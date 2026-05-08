#!/usr/bin/env python3
"""
동적 연도 기반 ROE 값 분석기 - 병렬 처리 버전 (v2)
"""

import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
import logging
import json
import warnings
import urllib3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# SSL 경고 억제
warnings.filterwarnings('ignore', message='.*OpenSSL.*')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 스레드 안전을 위한 락
lock = threading.Lock()

class StockROEAnalyzerFinal:
    def __init__(self, max_workers=10, batch_size=300):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        # 현재 연도 기반으로 목표 연도 설정
        current_year = datetime.now().year
        self.target_year = current_year
        self.target_period = f"{current_year}/12(E)"
        self.max_workers = max_workers
        self.batch_size = batch_size
        
        logger.info(f"현재 연도: {current_year}, 목표 기간: {self.target_period}")
        logger.info(f"병렬 처리 설정: 최대 워커 {max_workers}개, 배치 크기 {batch_size}개")
    
    def get_stock_list(self):
        """종목 리스트 가져오기"""
        try:
            from stock_list_manual import get_stock_list
            return get_stock_list()
        except ImportError:
            logger.error("stock_list_manual.py를 찾을 수 없습니다.")
            return pd.DataFrame()
    
    def get_fnguide_page(self, stock_code):
        """FnGuide에서 특정 종목 페이지 가져오기 (재시도 로직 포함)"""
        max_retries = 3
        retry_delay = 5  # 재시도 간 대기 시간 (초)
        
        for attempt in range(max_retries):
            try:
                url = f"https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?pGB=1&gicode=A{stock_code}&cID=&MenuYn=Y&ReportGB=&NewMenuID=11&stkGb=701"
                
                if attempt > 0:
                    logger.info(f"종목코드 {stock_code} 재시도 {attempt + 1}/{max_retries}...")
                else:
                    logger.info(f"종목코드 {stock_code} 페이지 요청 중...")
                
                response = self.session.get(url, timeout=15)  # 타임아웃 증가
                response.raise_for_status()
                
                logger.info("페이지 로드 성공")
                return BeautifulSoup(response.text, 'html.parser')
                
            except Exception as e:
                logger.error(f"종목코드 {stock_code} 페이지 로드 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                
                if attempt < max_retries - 1:
                    logger.info(f"{retry_delay}초 후 재시도...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 지수적 백오프
                else:
                    logger.error(f"종목코드 {stock_code} 최대 재시도 횟수 초과")
                    return None
        
        return None
    
    def find_target_year_column(self, header_cells):
        """헤더 셀 텍스트 리스트에서 target_year를 포함하는 컬럼 인덱스 반환. 없으면 None."""
        year_str = str(self.target_year)
        for idx, cell in enumerate(header_cells):
            if year_str in cell:
                return idx
        return None

    def find_roe_dynamic_year(self, soup, stock_code):
        """동적 연도 기반 ROE 값 찾기"""
        logger.info(f"종목코드 {stock_code}의 {self.target_period} ROE 값 검색 중...")
        
        try:
            tables = soup.find_all('table')
            logger.info(f"총 {len(tables)}개 테이블 발견")
            
            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')
                
                # 테이블 11과 같은 구조 찾기 (IFRS(연결) + Annual + Net Quarter)
                if len(rows) >= 20:  # 충분한 행이 있는 테이블
                    header_row = rows[0]
                    header_cells = header_row.find_all(['td', 'th'])
                    
                    # 헤더에서 IFRS(연결), Annual, Net Quarter 확인
                    header_texts = [cell.get_text(strip=True) for cell in header_cells]
                    
                    if ('IFRS(연결)' in header_texts and 
                        'Annual' in header_texts and 
                        'Net Quarter' in header_texts):
                        
                        logger.info(f"재무 테이블 발견! (테이블 {table_idx + 1})")
                        logger.info(f"헤더: {header_texts}")
                        
                        # 모든 헤더 셀의 상세 정보 출력
                        for idx, cell in enumerate(header_cells):
                            cell_text = cell.get_text(strip=True)
                            logger.info(f"  헤더 셀 {idx + 1}: '{cell_text}'")
                        
                        # ROE 행 찾기
                        for row_idx, row in enumerate(rows[1:], 1):
                            cells = row.find_all(['td', 'th'])
                            
                            if len(cells) >= 2:
                                first_cell_text = cells[0].get_text(strip=True)
                                
                                # ROE 관련 키워드 확인
                                if 'ROE' in first_cell_text:
                                    logger.info(f"ROE 행 발견! (테이블 {table_idx + 1}, 행 {row_idx + 1})")
                                    logger.info(f"제목: {first_cell_text}")
                                    
                                    # 모든 셀의 내용 출력 (디버깅용)
                                    for cell_idx, cell in enumerate(cells):
                                        cell_text = cell.get_text(strip=True)
                                        if cell_text:
                                            logger.info(f"  셀 {cell_idx + 1}: {cell_text}")
                                    
                                    # 2025년 데이터 (셀 5번째) 가져오기
                                    target_column_idx = 4  # 0-based index, 셀 5번째
                                    logger.info(f"2025년 데이터 컬럼 선택: 위치 {target_column_idx + 1}")
                                    
                                    # 목표 연도 컬럼의 ROE 값 가져오기
                                    if len(cells) > target_column_idx:
                                        cell_text = cells[target_column_idx].get_text(strip=True)
                                        logger.info(f"목표 연도 셀 내용: {cell_text}")
                                        
                                        # 숫자 추출
                                        roe_match = re.search(r'([\d.-]+)', cell_text)
                                        if roe_match:
                                            roe_value = float(roe_match.group(1))
                                            logger.info(f"{self.target_period} ROE 값 발견: {roe_value}%")
                                            return roe_value
                                        else:
                                            logger.warning(f"{self.target_period} ROE 값이 숫자가 아닙니다: {cell_text}")
                                            return 0.0
                                    else:
                                        logger.warning(f"목표 연도 컬럼 위치가 범위를 벗어났습니다.")
                                        return 0.0
            
            logger.warning(f"종목코드 {stock_code}의 {self.target_period} ROE 값을 찾지 못했습니다.")
            return 0.0
            
        except Exception as e:
            logger.error(f"종목코드 {stock_code} ROE 검색 실패: {e}")
            return None
    
    def analyze_single_stock(self, stock_data):
        """단일 종목 분석 (병렬 처리용)"""
        stock_code = stock_data['종목코드']
        stock_name = stock_data['종목명']
        market = stock_data['시장']
        
        try:
            # 페이지 가져오기
            soup = self.get_fnguide_page(stock_code)
            if not soup:
                logger.warning(f"? {stock_name}: 페이지를 가져올 수 없음")
                return {
                    '종목코드': stock_code,
                    '종목명': stock_name,
                    '시장': market,
                    f'{self.target_period}_ROE(%)': 0.0
                }
            
            # ROE 값 가져오기
            roe_value = self.find_roe_dynamic_year(soup, stock_code)
            
            # 결과 반환
            result = {
                '종목코드': stock_code,
                '종목명': stock_name,
                '시장': market,
                f'{self.target_period}_ROE(%)': roe_value
            }
            
            if roe_value > 0:
                logger.info(f"✓ {stock_name}: ROE {roe_value}%")
            else:
                logger.warning(f"? {stock_name}: ROE 값이 없음 (0%)")
            
            return result
            
        except Exception as e:
            logger.error(f"종목 {stock_name}({stock_code}) 분석 실패: {e}")
            return {
                '종목코드': stock_code,
                '종목명': stock_name,
                '시장': market,
                f'{self.target_period}_ROE(%)': 0.0
            }
    
    def analyze_stocks_roe_dynamic(self, max_stocks=None):
        """병렬 처리로 모든 종목의 ROE 분석"""
        # 종목 리스트 가져오기
        stocks_df = self.get_stock_list()
        
        if stocks_df.empty:
            logger.error("종목 리스트를 가져올 수 없습니다.")
            return pd.DataFrame()
        
        # 최대 종목 수 제한 (테스트용)
        if max_stocks:
            stocks_df = stocks_df.head(max_stocks)
        
        total_stocks = len(stocks_df)
        logger.info(f"총 {total_stocks}개 종목의 {self.target_period} ROE 병렬 분석을 시작합니다.")
        
        # 종목을 배치로 나누기
        batches = []
        for i in range(0, total_stocks, self.batch_size):
            batch = stocks_df.iloc[i:i+self.batch_size]
            batches.append(batch)
        
        logger.info(f"총 {len(batches)}개 배치로 나누어 처리합니다.")
        
        all_results = []
        success_count = 0
        fail_count = 0
        
        # 각 배치를 병렬로 처리
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for batch_idx, batch in enumerate(batches):
                logger.info(f"배치 {batch_idx + 1}/{len(batches)} 처리 시작 ({len(batch)}개 종목)")
                
                # 배치 내 종목들을 병렬로 처리
                batch_results = []
                futures = []
                
                for _, row in batch.iterrows():
                    future = executor.submit(self.analyze_single_stock, row)
                    futures.append(future)
                
                # 결과 수집
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        batch_results.append(result)
                        
                        if result[f'{self.target_period}_ROE(%)'] > 0:
                            success_count += 1
                        else:
                            fail_count += 1
                            
                    except Exception as e:
                        logger.error(f"배치 처리 중 오류: {e}")
                        fail_count += 1
                
                all_results.extend(batch_results)
                
                # 진행 상황 출력
                processed = len(all_results)
                logger.info(f"배치 {batch_idx + 1} 완료. 진행률: {processed}/{total_stocks} ({processed/total_stocks*100:.1f}%)")
                
                # 서버 부하 방지를 위한 배치 간 대기
                if batch_idx < len(batches) - 1:
                    time.sleep(2)
        
        # 결과를 DataFrame으로 변환
        results_df = pd.DataFrame(all_results)
        
        print(f"\n🎯 병렬 분석 완료! 성공: {success_count}개, 실패: {fail_count}개")
        logger.info(f"병렬 분석 완료! 성공: {success_count}개, 실패: {fail_count}개")
        
        if not results_df.empty:
            roe_column = f'{self.target_period}_ROE(%)'
            results_df = results_df.sort_values(roe_column, ascending=False)
            print(f"📊 ROE 분석 완료 종목: {len(results_df)}개")
            logger.info(f"ROE 분석 완료 종목: {len(results_df)}개")
        else:
            print("❌ ROE 값을 찾은 종목이 없습니다.")
            logger.info("ROE 값을 찾은 종목이 없습니다.")
        
        return results_df
    
    def save_results(self, results_df, filename=None):
        """결과를 파일로 저장"""
        if filename is None:
            filename = f"roe_{self.target_year}_parallel_results.csv"
        
        if not results_df.empty:
            # CSV 저장
            results_df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"결과가 {filename}에 저장되었습니다.")
            
            # JSON 저장
            json_filename = filename.replace('.csv', '.json')
            results_df.to_json(json_filename, orient='records', force_ascii=False, indent=2)
            logger.info(f"결과가 {json_filename}에도 저장되었습니다.")
        else:
            logger.warning("저장할 결과가 없습니다.")

def main():
    """메인 함수"""
    analyzer = StockROEAnalyzerFinal(max_workers=10, batch_size=300)
    
    try:
        # 테스트를 위해 처음 50개 종목 분석 (병렬 처리)
        results = analyzer.analyze_stocks_roe_dynamic(max_stocks=50)
        
        if not results.empty:
            print(f"\n=== {analyzer.target_period} ROE 병렬 분석 결과 ===")
            print(f"분석 완료 종목: {len(results)}개")
            print("\n" + "="*80)
            print(results.to_string(index=False))
            print("="*80)
            
            # 결과 저장
            analyzer.save_results(results)
        else:
            print("ROE 값을 찾은 종목이 없습니다.")
    
    except Exception as e:
        logger.error(f"분석 중 오류 발생: {e}")

if __name__ == "__main__":
    main() 