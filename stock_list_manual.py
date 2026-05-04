#!/usr/bin/env python3
"""
완전 자동화된 인터넷 스크래핑으로 종목 리스트 관리
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import logging
import os
import time
from datetime import datetime
import re

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class StockListManager:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        self.stock_file = 'stock_list_krx.csv'
    
    def get_stock_list_from_internet(self):
        """인터넷에서 종목 리스트 가져오기"""
        try:
            logger.info("인터넷에서 종목 리스트 가져오는 중...")
            
            # 네이버 금융에서 종목 리스트 스크래핑
            df = self.scrape_stocks_from_naver_finance()
            
            if not df.empty:
                # 중복 제거
                df = df.drop_duplicates(subset=['종목코드'], keep='first')
                
                # 종목코드를 6자리로 맞추기
                df['종목코드'] = df['종목코드'].astype(str).str.zfill(6)
                
                # 시장 컬럼이 없으면 기본값 설정
                if '시장' not in df.columns:
                    df['시장'] = 'KOSPI'
                
                logger.info(f"총 {len(df)}개 종목 가져옴")
                return df
            else:
                logger.error("인터넷에서 종목 데이터를 가져올 수 없습니다.")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"인터넷에서 종목 리스트 가져오기 실패: {e}")
            return pd.DataFrame()
    
    def scrape_stocks_from_naver_finance(self):
        """네이버 금융에서 종목 리스트 스크래핑"""
        try:
            logger.info("네이버 금융에서 종목 리스트 스크래핑 중...")
            
            stocks = []
            
            # KOSPI 전체 페이지 스크래핑
            logger.info("KOSPI 종목 스크래핑 시작...")
            kospi_stocks = self.scrape_market_stocks("https://finance.naver.com/sise/sise_market_sum.nhn", "KOSPI")
            stocks.extend(kospi_stocks)
            
            # KOSDAQ 전체 페이지 스크래핑
            logger.info("KOSDAQ 종목 스크래핑 시작...")
            kosdaq_stocks = self.scrape_market_stocks("https://finance.naver.com/sise/sise_market_sum.nhn?sosok=1", "KOSDAQ")
            stocks.extend(kosdaq_stocks)
            
            if stocks:
                # 중복 제거
                df = pd.DataFrame(stocks)
                df = df.drop_duplicates(subset=['종목코드'], keep='first')
                logger.info(f"네이버 금융에서 총 {len(df)}개 종목 발견")
                return df
            else:
                logger.warning("네이버 금융에서 종목을 찾을 수 없습니다.")
                return pd.DataFrame()
                
        except Exception as e:
            logger.error(f"네이버 금융 스크래핑 실패: {e}")
            return pd.DataFrame()
    
    def scrape_market_stocks(self, base_url, market_name):
        """특정 시장의 모든 종목 스크래핑"""
        stocks = []
        page = 1
        total_pages = 1  # 초기값
        
        while page <= total_pages:
            try:
                if page == 1:
                    url = base_url
                else:
                    # KOSPI의 경우 첫 번째 페이지는 page 파라미터가 없고, 두 번째부터는 page 파라미터가 있음
                    if "sosok=1" not in base_url:  # KOSPI
                        url = f"{base_url}?page={page}"
                    else:  # KOSDAQ
                        url = f"{base_url}&page={page}"
                
                logger.info(f"{market_name} 페이지 {page} 스크래핑 중...")
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                response.encoding = 'euc-kr'
                
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # 첫 번째 페이지에서 전체 페이지 수 확인
                if page == 1:
                    total_pages = self.get_total_pages(soup)
                    logger.info(f"{market_name} 총 {total_pages}페이지 발견")
                
                # 종목 테이블 찾기
                table = soup.find('table', {'class': 'type_2'})
                if not table:
                    tables = soup.find_all('table')
                    for t in tables:
                        if t.find('tr', {'class': 'type1'}) or t.find('tr', {'class': 'type2'}):
                            table = t
                            break
                
                if table:
                    page_stocks = []
                    rows = table.find_all('tr')
                    for row in rows:
                        # 헤더 행 건너뛰기
                        if row.get('class') and ('type1' in row.get('class') or 'type2' in row.get('class')):
                            continue
                        
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            try:
                                stock_code = ""
                                stock_name = ""
                                
                                # 두 번째 셀 (종목명)에서 링크 찾기
                                if len(cells) > 1:
                                    second_cell = cells[1]
                                    link = second_cell.find('a')
                                    if link:
                                        href = link.get('href', '')
                                        stock_name = link.get_text(strip=True)
                                        
                                        # href에서 종목코드 추출
                                        if 'code=' in href:
                                            code_match = re.search(r'code=(\d{6})', href)
                                            if code_match:
                                                stock_code = code_match.group(1)
                                
                                # 종목코드가 6자리 숫자인지 확인하고 종목명이 있는지 확인
                                if re.match(r'^\d{6}$', stock_code) and stock_name and len(stock_name) > 0:
                                    # 중복 체크 (현재 페이지와 이전 페이지 모두 확인)
                                    existing_codes = [s['종목코드'] for s in stocks] + [s['종목코드'] for s in page_stocks]
                                    if stock_code not in existing_codes:
                                        page_stocks.append({
                                            '종목코드': stock_code,
                                            '종목명': stock_name,
                                            '시장': market_name
                                        })
                            except Exception as e:
                                logger.debug(f"행 처리 중 오류: {e}")
                                continue
                    
                    stocks.extend(page_stocks)
                    logger.info(f"{market_name} 페이지 {page}에서 {len(page_stocks)}개 종목 발견 (누적: {len(stocks)}개)")
                else:
                    logger.warning(f"{market_name} 페이지 {page}에서 종목 테이블을 찾을 수 없습니다.")
                
                page += 1
                
                # 너무 빠른 요청 방지
                time.sleep(0.5)
                
            except Exception as e:
                logger.warning(f"{market_name} 페이지 {page} 스크래핑 실패: {e}")
                page += 1
        
        return stocks
    
    def get_total_pages(self, soup):
        """페이지에서 전체 페이지 수 추출"""
        try:
            # 페이지 네비게이션에서 마지막 페이지 번호 찾기
            navi_table = soup.find('table', {'class': 'Nnavi'})
            if navi_table:
                links = navi_table.find_all('a')
                if links:
                    # "맨뒤" 링크에서 페이지 번호 추출
                    for link in links:
                        text = link.get_text(strip=True)
                        href = link.get('href', '')
                        if text == '맨뒤':
                            match = re.search(r'page=(\d+)', href)
                            if match:
                                return int(match.group(1))
                    
                    # 마지막 링크의 텍스트가 페이지 번호인지 확인
                    last_link = links[-1]
                    page_text = last_link.get_text(strip=True)
                    if page_text.isdigit():
                        return int(page_text)
            
            # 대안: 페이지 번호가 있는 모든 링크 찾기
            all_links = soup.find_all('a', href=re.compile(r'page=\d+'))
            if all_links:
                page_numbers = []
                for link in all_links:
                    href = link.get('href', '')
                    match = re.search(r'page=(\d+)', href)
                    if match:
                        page_numbers.append(int(match.group(1)))
                
                if page_numbers:
                    return max(page_numbers)  # 최대 페이지 번호
            
            # 기본값: 50페이지 (대략적인 추정)
            return 50
            
        except Exception as e:
            logger.warning(f"전체 페이지 수 추출 실패: {e}")
            return 50  # 기본값
    

    
    def save_stock_list(self, stock_list):
        """종목 리스트를 CSV 파일에 저장"""
        try:
            if not stock_list.empty:
                stock_list.to_csv(self.stock_file, index=False, encoding='utf-8-sig')
                logger.info(f"종목 리스트가 {self.stock_file}에 저장되었습니다.")
                return True
            else:
                logger.warning("저장할 종목 리스트가 없습니다.")
                return False
        except Exception as e:
            logger.error(f"종목 리스트 저장 실패: {e}")
            return False
    
    def load_stock_list_from_file(self):
        """CSV 파일에서 종목 리스트 읽기"""
        try:
            if os.path.exists(self.stock_file):
                stock_list = pd.read_csv(self.stock_file, encoding='utf-8-sig')
                # 종목코드를 6자리로 맞추기
                stock_list['종목코드'] = stock_list['종목코드'].astype(str).str.zfill(6)
                # 시장 컬럼이 없으면 기본값 설정
                if '시장' not in stock_list.columns:
                    stock_list['시장'] = 'KOSPI'
                logger.info(f"파일에서 {len(stock_list)}개 종목 읽어옴: {self.stock_file}")
                return stock_list
            else:
                logger.info(f"종목 리스트 파일이 없습니다: {self.stock_file}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"파일에서 종목 리스트 읽기 실패: {e}")
            return pd.DataFrame()
    
    def get_stock_list(self):
        """종목 리스트 가져오기 (CSV 파일 우선, 없으면 인터넷에서 가져오기)"""
        # 먼저 CSV 파일에서 읽기 시도
        stock_list = self.load_stock_list_from_file()
        
        if not stock_list.empty:
            logger.info("저장된 CSV 파일에서 종목 리스트를 사용합니다.")
            return stock_list
        
        # CSV 파일이 없으면 인터넷에서 가져오기
        logger.info("저장된 CSV 파일이 없어서 인터넷에서 종목 리스트를 가져옵니다.")
        stock_list = self.get_stock_list_from_internet()
        
        if not stock_list.empty:
            # 가져온 데이터를 CSV 파일에 저장
            self.save_stock_list(stock_list)
            return stock_list
        else:
            logger.error("인터넷에서도 종목 리스트를 가져올 수 없습니다.")
            return pd.DataFrame()

def get_stock_list():
    """종목 리스트 가져오기 함수 (기존 호환성 유지)"""
    stock_manager = StockListManager()
    return stock_manager.get_stock_list()

if __name__ == "__main__":
    # 테스트 실행
    stock_manager = StockListManager()
    stock_list = stock_manager.get_stock_list()
    
    if not stock_list.empty:
        print(f"총 {len(stock_list)}개 종목:")
        print(stock_list.head(10))
        
        # 시장별 분포
        if '시장' in stock_list.columns:
            market_dist = stock_list['시장'].value_counts()
            print(f"\n시장별 분포:")
            for market, count in market_dist.items():
                print(f"  {market}: {count}개")
        else:
            print(f"\n시장 정보 없음 (기본값: KOSPI)")
    else:
        print("종목 리스트를 가져올 수 없습니다.") 