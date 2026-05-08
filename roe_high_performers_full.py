#!/usr/bin/env python3
"""
ROE 10% 이상 고성과 종목 찾기 - 완전 버전
"""

import pandas as pd
import logging
from stock_roe_analyzer_final import StockROEAnalyzerFinal

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ROEHighPerformersFull:
    def __init__(self, roe_threshold=10.0, analyzer=None):
        self.analyzer = analyzer if analyzer is not None else StockROEAnalyzerFinal()
        self.roe_threshold = roe_threshold
        self.target_period = self.analyzer.target_period
        
    def find_high_roe_stocks(self):
        """ROE 임계값 이상인 종목들 찾기"""
        logger.info(f"ROE {self.roe_threshold}% 이상 종목 검색 시작...")
        
        # 모든 종목 분석
        all_results = self.analyzer.analyze_stocks_roe_dynamic(max_stocks=None)
        
        if all_results.empty:
            logger.warning("분석된 종목이 없습니다.")
            return pd.DataFrame()
        
        # ROE 임계값 이상인 종목 필터링
        roe_column = f'{self.target_period}_ROE(%)'
        high_roe_stocks = all_results[all_results[roe_column] >= self.roe_threshold].copy()
        
        # ROE 기준으로 내림차순 정렬
        high_roe_stocks = high_roe_stocks.sort_values(roe_column, ascending=False)
        
        logger.info(f"ROE {self.roe_threshold}% 이상 종목: {len(high_roe_stocks)}개")
        
        return high_roe_stocks
    
    def print_results(self, high_roe_stocks):
        """결과 출력"""
        if high_roe_stocks.empty:
            print(f"\n❌ ROE {self.roe_threshold}% 이상인 종목이 없습니다.")
            return
        
        roe_column = f'{self.target_period}_ROE(%)'
        
        print(f"\n🎯 ROE {self.roe_threshold}% 이상 고성과 종목 ({len(high_roe_stocks)}개)")
        print("=" * 80)
        print(f"{'순위':<4} {'종목코드':<8} {'종목명':<15} {'시장':<8} {roe_column}")
        print("-" * 80)
        
        for idx, (_, row) in enumerate(high_roe_stocks.iterrows(), 1):
            stock_code = row['종목코드']
            stock_name = row['종목명']
            market = row['시장']
            roe_value = row[roe_column]
            
            print(f"{idx:<4} {stock_code:<8} {stock_name:<15} {market:<8} {roe_value:>6.2f}%")
        
        print("=" * 80)
        
        # 통계 정보
        avg_roe = high_roe_stocks[roe_column].mean()
        max_roe = high_roe_stocks[roe_column].max()
        min_roe = high_roe_stocks[roe_column].min()
        
        print(f"📊 통계 정보:")
        print(f"   평균 ROE: {avg_roe:.2f}%")
        print(f"   최고 ROE: {max_roe:.2f}%")
        print(f"   최저 ROE: {min_roe:.2f}%")
        
        # 시장별 분포
        market_dist = high_roe_stocks['시장'].value_counts()
        print(f"\n📈 시장별 분포:")
        for market, count in market_dist.items():
            print(f"   {market}: {count}개")
        
        # ROE 구간별 분포
        print(f"\n📊 ROE 구간별 분포:")
        roe_ranges = [
            (10, 15, "10-15%"),
            (15, 20, "15-20%"),
            (20, 30, "20-30%"),
            (30, 50, "30-50%"),
            (50, float('inf'), "50%+")
        ]
        
        for min_val, max_val, label in roe_ranges:
            if max_val == float('inf'):
                count = len(high_roe_stocks[high_roe_stocks[roe_column] >= min_val])
            else:
                count = len(high_roe_stocks[(high_roe_stocks[roe_column] >= min_val) & (high_roe_stocks[roe_column] < max_val)])
            if count > 0:
                print(f"   {label}: {count}개")
    
    def save_high_roe_results(self, high_roe_stocks, filename=None):
        """고성과 종목 결과 저장"""
        if filename is None:
            filename = f"roe_{self.roe_threshold}plus_{self.analyzer.target_year}_full_results.csv"
        
        if not high_roe_stocks.empty:
            # CSV 저장
            high_roe_stocks.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"고성과 종목 결과가 {filename}에 저장되었습니다.")
        else:
            logger.warning("저장할 고성과 종목이 없습니다.")

def main():
    """메인 함수"""
    print("🚀 ROE 고성과 종목 검색 프로그램 (완전 버전)")
    print("=" * 60)
    
    # ROE 임계값 설정 (10% 이상)
    roe_threshold = 10.0
    
    try:
        # 고성과 종목 찾기
        finder = ROEHighPerformersFull(roe_threshold=roe_threshold)
        
        # 모든 종목 분석
        print(f"📊 {finder.target_period} 기준 ROE {roe_threshold}% 이상 종목 검색 중...")
        print("⚠️  모든 종목을 분석하므로 시간이 오래 걸릴 수 있습니다.")
        
        high_roe_stocks = finder.find_high_roe_stocks()
        
        # 결과 출력
        finder.print_results(high_roe_stocks)
        
        # 결과 저장
        finder.save_high_roe_results(high_roe_stocks)
        
        print(f"\n✅ 분석 완료! 결과가 파일로 저장되었습니다.")
        
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {e}")
        print(f"\n❌ 오류가 발생했습니다: {e}")

if __name__ == "__main__":
    main() 