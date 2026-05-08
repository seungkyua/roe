#!/usr/bin/env python3
"""
S-RIM 파이프라인: ROE CSV + 재무 데이터 CSV → 적정 주가 계산
discount_rate는 KIS Rating 사이트에서 BBB- 5년 금리를 자동으로 가져옴
"""

import argparse
import logging
import requests
import pandas as pd
from bs4 import BeautifulSoup
from s_rim import SRIMCalculator

logger = logging.getLogger(__name__)

KIS_RATING_URL = "https://www.kisrating.com/ratingsStatistics/statics_spread.do"


def _get_kis_rating_page() -> BeautifulSoup:
    """KIS Rating 등급별 금리스프레드 페이지 가져오기"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'ko-KR,ko;q=0.9',
    })
    resp = session.get(KIS_RATING_URL, timeout=15)
    resp.raise_for_status()
    resp.encoding = 'utf-8'
    return BeautifulSoup(resp.text, 'html.parser')


def fetch_discount_rate() -> float:
    """
    KIS Rating 등급별 금리스프레드 표에서 BBB- 5년 금리를 가져온다.
    테이블[0]: 구분 | 3월 | 6월 | 9월 | 1년 | 1년6월 | 2년 | 3년 | 5년
    BBB- 행의 5년 컬럼 값을 반환 (단위: %)
    """
    soup = _get_kis_rating_page()
    tables = soup.find_all('table')
    if not tables:
        raise ValueError("KIS Rating 페이지에서 테이블을 찾을 수 없습니다.")

    table = tables[0]
    rows = table.find_all('tr')

    # 헤더에서 '5년' 컬럼 인덱스 찾기
    header_cells = rows[0].find_all(['th', 'td'])
    header_texts = [c.get_text(strip=True) for c in header_cells]
    try:
        col_idx = header_texts.index('5년')
    except ValueError:
        raise ValueError(f"'5년' 컬럼을 찾을 수 없습니다. 헤더: {header_texts}")

    # BBB- 행 탐색
    for row in rows[1:]:
        cells = row.find_all(['th', 'td'])
        if not cells:
            continue
        if cells[0].get_text(strip=True) == 'BBB-':
            val_str = cells[col_idx].get_text(strip=True).replace(',', '')
            rate = float(val_str)
            logger.info(f"KIS Rating BBB- 5년 금리: {rate}%")
            return rate

    raise ValueError("BBB- 행을 찾을 수 없습니다.")


def merge_inputs(roe_df: pd.DataFrame, fundamentals_df: pd.DataFrame) -> pd.DataFrame:
    """두 DataFrame을 종목코드 기준 inner join으로 병합"""
    return pd.merge(roe_df, fundamentals_df, on='종목코드', how='inner')


class SRIMPipeline:
    def __init__(self, roe_csv: str, fundamentals_csv: str):
        self.roe_csv = roe_csv
        self.fundamentals_csv = fundamentals_csv
        self.discount_rate = fetch_discount_rate()
        self.calculator = SRIMCalculator(self.discount_rate)
        logger.info(f"할인율(BBB- 5년): {self.discount_rate}%")

    def load(self) -> pd.DataFrame:
        roe_df = pd.read_csv(self.roe_csv, encoding='utf-8-sig', dtype={'종목코드': str})
        fundamentals_df = pd.read_csv(self.fundamentals_csv, encoding='utf-8-sig', dtype={'종목코드': str})
        roe_df['종목코드'] = roe_df['종목코드'].str.zfill(6)
        fundamentals_df['종목코드'] = fundamentals_df['종목코드'].str.zfill(6)
        # YYYY/12(E)_ROE(%) 형식의 컬럼을 ROE(%)로 정규화
        roe_col = next((c for c in roe_df.columns if c.endswith('_ROE(%)')), None)
        if roe_col:
            roe_df = roe_df.rename(columns={roe_col: 'ROE(%)'})
        return merge_inputs(roe_df, fundamentals_df)

    def run(self) -> pd.DataFrame:
        """병합 데이터에 S-RIM 계산 적용 후 결과 DataFrame 반환"""
        merged = self.load()
        results = [self.calculator.calc_row(row) for row in merged.to_dict('records')]
        df = pd.DataFrame(results)
        # 사용된 할인율 컬럼 추가
        df['할인율(%)'] = self.discount_rate
        return df

    def save(self, results: pd.DataFrame, filename: str):
        results.to_csv(filename, index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    parser = argparse.ArgumentParser(description='S-RIM 적정 주가 계산 파이프라인')
    parser.add_argument('--roe-csv', required=True)
    parser.add_argument('--fundamentals-csv', required=True)
    args = parser.parse_args()

    pipeline = SRIMPipeline(args.roe_csv, args.fundamentals_csv)
    results = pipeline.run()
    out = f"srim_results_{pipeline.discount_rate}.csv"
    pipeline.save(results, out)
    print(results.to_string(index=False))
    print(f"\n할인율: {pipeline.discount_rate}%")
    print(f"결과 저장: {out}")
