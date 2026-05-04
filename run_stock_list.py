#!/usr/bin/env python3
"""
전체 주식 리스트를 가져오는 실행 파일
stock_list_manual.py의 StockListManager를 사용하여 인터넷에서 종목 리스트를 가져옵니다.
"""

import sys
import os
import pandas as pd
from datetime import datetime

# stock_list_manual.py에서 StockListManager 클래스 가져오기
from stock_list_manual import StockListManager

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("전체 주식 리스트 가져오기 시작")
    print("=" * 60)
    print(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    try:
        # StockListManager 인스턴스 생성
        stock_manager = StockListManager()
        
        print("1. 인터넷에서 종목 리스트 가져오는 중...")
        print("   - 네이버 금융에서 KOSPI, KOSDAQ 종목 스크래핑")
        print("   - 시가총액 상위 종목들 우선 수집")
        print()
        
        # 종목 리스트 가져오기
        stock_list = stock_manager.get_stock_list()
        
        if not stock_list.empty:
            print("2. 종목 리스트 가져오기 완료!")
            print(f"   - 총 {len(stock_list)}개 종목 발견")
            print()
            
            # 기본 정보 출력
            print("3. 종목 리스트 요약:")
            print(f"   - 파일 저장 위치: {stock_manager.stock_file}")
            print(f"   - 데이터 형식: {stock_list.shape[0]}행 x {stock_list.shape[1]}열")
            print()
            
            # 컬럼 정보 출력
            print("4. 데이터 컬럼:")
            for i, col in enumerate(stock_list.columns, 1):
                print(f"   {i}. {col}")
            print()
            
            # 시장별 분포 출력
            if '시장' in stock_list.columns:
                print("5. 시장별 종목 분포:")
                market_dist = stock_list['시장'].value_counts()
                for market, count in market_dist.items():
                    print(f"   - {market}: {count}개")
            else:
                print("5. 시장 정보: 기본값 (KOSPI)")
            print()
            
            # 상위 10개 종목 출력
            print("6. 상위 10개 종목:")
            print("   " + "-" * 50)
            for i, (_, row) in enumerate(stock_list.head(10).iterrows(), 1):
                print(f"   {i:2d}. {row['종목코드']} - {row['종목명']}")
            print()
            
            # 파일 저장 확인
            if os.path.exists(stock_manager.stock_file):
                file_size = os.path.getsize(stock_manager.stock_file)
                print(f"7. 파일 저장 완료:")
                print(f"   - 파일명: {stock_manager.stock_file}")
                print(f"   - 파일 크기: {file_size:,} bytes")
                print(f"   - 저장 시간: {datetime.fromtimestamp(os.path.getmtime(stock_manager.stock_file)).strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print("7. 파일 저장 실패")
            print()
            
            print("=" * 60)
            print("종목 리스트 가져오기 완료!")
            print("=" * 60)
            
            return True
            
        else:
            print("❌ 오류: 종목 리스트를 가져올 수 없습니다.")
            print("   - 인터넷 연결을 확인해주세요.")
            print("   - 네이버 금융 웹사이트 접근이 가능한지 확인해주세요.")
            return False
            
    except ImportError as e:
        print(f"❌ 오류: stock_list_manual.py 파일을 찾을 수 없습니다.")
        print(f"   - 오류 내용: {e}")
        return False
        
    except Exception as e:
        print(f"❌ 오류: 예상치 못한 오류가 발생했습니다.")
        print(f"   - 오류 내용: {e}")
        return False

def show_usage():
    """사용법 출력"""
    print("사용법:")
    print("  python run_stock_list.py")
    print()
    print("기능:")
    print("  - 네이버 금융에서 전체 주식 리스트 가져오기")
    print("  - KOSPI, KOSDAQ 시가총액 상위 종목 수집")
    print("  - CSV 파일로 저장 (stock_list_krx.csv)")
    print("  - 상세한 실행 결과 출력")

if __name__ == "__main__":
    # 명령행 인수 확인
    if len(sys.argv) > 1 and sys.argv[1] in ['-h', '--help', 'help']:
        show_usage()
    else:
        # 메인 실행
        success = main()
        
        # 종료 코드 설정
        sys.exit(0 if success else 1)
