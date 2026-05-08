#!/usr/bin/env python3
"""
주식 추천 프로그램: 예상적정주가(S-RIM) 대비 현재가 상승여력 기준 종목 추천
현재가: Naver Finance (https://finance.naver.com/item/main.naver?code={종목코드})
입력:  srim_results_*.csv
출력:  stock_recommendations.csv
"""

import argparse
import logging
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NAVER_PRICE_URL = "https://finance.naver.com/item/main.naver?code={code}"

OUTPUT_COLUMNS = [
    '종목코드', '종목명', '시장',
    'ROE(%)', '예상ROE(%)',
    '현재가',
    '적정주가(S-RIM)', '보수적주가(S-RIM)',
    '예상적정주가(S-RIM)', '예상보수적주가(S-RIM)',
    '상승여력(%)',
]


def _get_naver_price_page(stock_code: str, session: requests.Session):
    """Naver Finance 종목 페이지 가져오기"""
    try:
        url = NAVER_PRICE_URL.format(code=stock_code)
        resp = session.get(url, timeout=10)
        resp.raise_for_status()
        resp.encoding = 'euc-kr'
        return BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        logger.warning(f"{stock_code} 현재가 페이지 로드 실패: {e}")
        return None


def fetch_current_price(stock_code: str, session: requests.Session = None) -> int:
    """Naver Finance에서 종목 현재가 반환 (실패 시 0)"""
    if session is None:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9',
        })

    soup = _get_naver_price_page(stock_code, session)
    if soup is None:
        return 0

    el = soup.select_one('.no_today .blind')
    if el:
        val = el.get_text(strip=True).replace(',', '')
        if val.isdigit():
            return int(val)

    logger.warning(f"{stock_code}: 현재가 파싱 실패")
    return 0


class StockRecommender:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'ko-KR,ko;q=0.9',
        })

    def load_srim_results(self, csv_path: str) -> pd.DataFrame:
        """S-RIM 결과 CSV 로드. 예상적정주가가 있는 종목만 유지."""
        df = pd.read_csv(csv_path, encoding='utf-8-sig', dtype={'종목코드': str})
        df['종목코드'] = df['종목코드'].str.zfill(6)
        return df

    def fetch_all_prices(self, stock_codes: list) -> dict:
        """종목 리스트의 현재가를 병렬로 가져온다. {종목코드: 현재가} 반환"""
        prices = {}
        total = len(stock_codes)

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(fetch_current_price, code, self.session): code
                for code in stock_codes
            }
            for i, future in enumerate(as_completed(futures), 1):
                code = futures[future]
                try:
                    price = future.result()
                    prices[code] = price
                    if i % 20 == 0 or i == total:
                        logger.info(f"현재가 조회 진행: {i}/{total}")
                except Exception as e:
                    logger.warning(f"{code} 현재가 조회 실패: {e}")
                    prices[code] = 0
                # Naver 서버 부하 방지
                time.sleep(0.05)

        return prices

    def calculate_upside(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        예상적정주가(S-RIM) 대비 현재가 상승여력(%) 계산.
        예상ROE(%)가 없는 종목(예상적정주가=0) 및 현재가=0인 종목은 제외.
        상승여력(%) 내림차순 정렬.
        """
        df = df[(df['예상적정주가(S-RIM)'] > 0) & (df['현재가'] > 0)].copy()
        df['상승여력(%)'] = (
            (df['예상적정주가(S-RIM)'] - df['현재가']) / df['현재가'] * 100
        ).round(2)
        df = df.sort_values('상승여력(%)', ascending=False)
        return df.reset_index(drop=True)

    def run(self, srim_csv: str, output_csv: str) -> pd.DataFrame:
        """전체 파이프라인: 현재가 수집 → 상승여력 계산 → 저장"""
        df = self.load_srim_results(srim_csv)
        logger.info(f"S-RIM 결과 로드: {len(df)}개 종목")

        # 현재가 수집
        logger.info("Naver Finance에서 현재가 수집 중...")
        prices = self.fetch_all_prices(df['종목코드'].tolist())
        df['현재가'] = df['종목코드'].map(prices).fillna(0).astype(int)

        # 상승여력 계산 및 정렬
        result = self.calculate_upside(df)

        # 출력 컬럼 선택 및 저장
        save_cols = [c for c in OUTPUT_COLUMNS if c in result.columns]
        result[save_cols].to_csv(output_csv, index=False, encoding='utf-8-sig')
        logger.info(f"추천 종목 저장: {output_csv} ({len(result)}개)")
        return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='S-RIM 기반 주식 추천')
    parser.add_argument('--srim-csv', required=True, help='S-RIM 결과 CSV')
    parser.add_argument('--output', default='stock_recommendations.csv')
    parser.add_argument('--top', type=int, default=50, help='상위 N개 출력')
    parser.add_argument('--workers', type=int, default=10)
    args = parser.parse_args()

    rec = StockRecommender(max_workers=args.workers)
    result = rec.run(args.srim_csv, args.output)

    display_cols = [c for c in OUTPUT_COLUMNS if c in result.columns]
    top = result[display_cols].head(args.top)

    print(f"\n📈 S-RIM 예상 상승여력 상위 {min(args.top, len(result))}개 종목")
    print("=" * 100)
    print(top.to_string(index=False))
    print("=" * 100)
    print(f"\n저장 파일: {args.output}")
