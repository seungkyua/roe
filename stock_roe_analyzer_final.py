#!/usr/bin/env python3
"""
동적 연도 기반 ROE 값 분석기 - 병렬 처리 버전 (v2)
"""

import pandas as pd
import requests
import time
import logging
import json
import importlib
import warnings
import urllib3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

import fnguide

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
            # 파일명이 숫자로 시작하므로 import 문 대신 importlib 로 불러온다
            stock_list_manual = importlib.import_module("01_stock_list_manual")
            return stock_list_manual.get_stock_list()
        except ImportError:
            logger.error("01_stock_list_manual.py를 찾을 수 없습니다.")
            return pd.DataFrame()
    
    def get_fnguide_financial(self, stock_code):
        """FnGuide 재무 하이라이트(연결, 연간) dataset 가져오기. 데이터가 없으면 None."""
        return fnguide.get_financial(self.session, stock_code, freq_typ='A')

    def find_roe_from_financial(self, dataset, stock_code):
        """재무 dataset 에서 target_year 컬럼의 ROE 값 추출. 없으면 0.0."""
        header_yymm = [h.get('YYMM') or '' for h in dataset.get('header', [])]
        # 연간 컬럼이 분기 컬럼보다 앞에 오므로 첫 번째로 일치하는 컬럼이 연간 값이다
        target_idx = self.find_target_year_column(header_yymm)
        if target_idx is None:
            logger.warning(f"종목코드 {stock_code}: {self.target_year}년 컬럼이 없습니다. {header_yymm}")
            return 0.0

        roe_row = fnguide.find_row(dataset, 'ROE')
        if roe_row is None:
            logger.warning(f"종목코드 {stock_code}: ROE 행을 찾지 못했습니다.")
            return 0.0

        roe_value = fnguide.to_float(roe_row.get(dataset['header'][target_idx].get('CD')))
        if roe_value is None:
            logger.warning(f"종목코드 {stock_code}: {self.target_period} ROE 값이 비어 있습니다.")
            return 0.0
        logger.info(f"종목코드 {stock_code}: {self.target_period} ROE 값 발견: {roe_value}%")
        return roe_value

    def find_target_year_column(self, header_cells):
        """헤더 셀 텍스트 리스트에서 target_year를 포함하는 컬럼 인덱스 반환. 없으면 None."""
        year_str = str(self.target_year)
        for idx, cell in enumerate(header_cells):
            if year_str in cell:
                return idx
        return None

    def analyze_single_stock(self, stock_data):
        """단일 종목 분석 (병렬 처리용)"""
        stock_code = stock_data['종목코드']
        stock_name = stock_data['종목명']
        market = stock_data['시장']
        
        try:
            # 재무 데이터 가져오기
            dataset = self.get_fnguide_financial(stock_code)
            if not dataset:
                logger.warning(f"? {stock_name}: 재무 데이터를 가져올 수 없음")
                return {
                    '종목코드': stock_code,
                    '종목명': stock_name,
                    '시장': market,
                    f'{self.target_period}_ROE(%)': 0.0
                }
            
            # ROE 값 가져오기
            roe_value = self.find_roe_from_financial(dataset, stock_code)
            
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