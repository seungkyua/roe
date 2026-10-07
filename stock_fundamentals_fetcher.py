#!/usr/bin/env python3
"""
FnGuide에서 종목별 자본총계(지배주주지분)와 총주식수를 수집
- Snapshot HTML : https://wcomp.fnguide.com/CompanyInfo/Snapshot?cmp_cd={code} (발행주식수, 자사주)
- 재무 API      : https://wcomp.fnguide.com/CompanyInfo/getSnpFinancial (지배주주지분, 예상 ROE)
"""

import time
import logging
import warnings
import urllib3
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import fnguide

warnings.filterwarnings('ignore', message='.*OpenSSL.*')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

class StockFundamentalsFetcher:
    def __init__(self, max_workers: int = 5):
        self.current_year = datetime.now().year
        self.max_workers = max_workers
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'ko-KR,ko;q=0.9',
        })

    # ── 페이지 fetch ───────────────────────────────────────────────────────────

    def get_page(self, stock_code: str):
        """Snapshot HTML (시세현황, 주주구분 현황 포함)"""
        for attempt in range(3):
            try:
                resp = self.session.get(fnguide.SNAPSHOT_URL, params={'cmp_cd': stock_code}, timeout=15)
                resp.raise_for_status()
                resp.encoding = 'utf-8'
                return BeautifulSoup(resp.text, 'html.parser')
            except Exception as e:
                logger.warning(f"{stock_code} 페이지 로드 실패 (시도 {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
        return None

    def get_financial(self, stock_code: str):
        """연간 8개 컬럼(실적 + 컨센서스 추정치) 재무 dataset"""
        return fnguide.get_financial(self.session, stock_code, freq_typ='Y')

    # ── 파싱 메서드 ────────────────────────────────────────────────────────────

    def find_issued_shares(self, soup) -> int:
        """시세현황 표에서 발행주식수(보통주) 반환"""
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                if '발행주식수' in cells[0].get_text(strip=True) and len(cells) > 1:
                    # cells[1] = '5,846,278,608/ 802,371,203'
                    val = cells[1].get_text(strip=True).split('/')[0].strip().replace(',', '')
                    if val.isdigit():
                        return int(val)
        logger.warning("발행주식수를 찾지 못했습니다.")
        return 0

    def find_treasury_shares(self, soup) -> int:
        """주주구분 현황 표에서 자기주식(자사주+자사주신탁) 보통주 반환.
        자기주식 행이 없으면 0 반환 (자기주식 없는 종목은 정상)."""
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                label = cells[0].get_text(strip=True)
                # 구버전: '자기주식 (자사주+자사주신탁)', 신버전: '자사주(자사주+자사주신탁)'
                if ('자기주식' in label or label.startswith('자사주(')) and len(cells) > 2:
                    val = cells[2].get_text(strip=True).replace(',', '')
                    if val.isdigit():
                        return int(val)
        return 0

    @staticmethod
    def _actual_columns(dataset):
        """실적(추정 E/잠정 P 아님) 컬럼의 값 키 목록 (VAL1, VAL2, ...)"""
        return [h['CD'] for h in dataset.get('header', [])
                if (h.get('EP_CHK') or '').strip() not in ('E', 'P')]

    def find_equity_from_financial(self, dataset, stock_code: str) -> float:
        """가장 최신 실적 연도의 자본총계(지배) 를 억원 → 원으로 변환. 없으면 0.0.
        비12월 결산 종목도 실적 컬럼 중 마지막을 사용하므로 올바르게 처리된다."""
        row = fnguide.find_row(dataset, '자본총계(지배)')
        actual = self._actual_columns(dataset)
        if row and actual:
            value = fnguide.to_float(row.get(actual[-1]))
            if value is not None:
                return value * 1e8  # 억원 → 원
        logger.warning(f"{stock_code}: 지배주주지분 값을 찾지 못했습니다.")
        return 0.0

    def find_future_roe_from_financial(self, dataset, stock_code: str) -> float:
        """
        연간 8개 컬럼 dataset 에서 미래 예상 ROE 계산.
          지배주주순이익 = 마지막(가장 미래) 컬럼
          전기말/당기말 지배주주지분 = 값이 있는 마지막 두 컬럼
          예상ROE(%) = 지배주주순이익 / ((전기말 + 당기말) / 2) * 100
        """
        header = dataset.get('header', [])
        net_row = fnguide.find_row(dataset, '당기순이익(지배)')
        equity_row = fnguide.find_row(dataset, '자본총계(지배)')
        if header and net_row and equity_row:
            net_income = fnguide.to_float(net_row.get(header[-1]['CD']))
            equities = [v for v in (fnguide.to_float(equity_row.get(h['CD'])) for h in header) if v is not None]
            if net_income and len(equities) >= 2:
                avg_equity = (equities[-2] + equities[-1]) / 2
                if avg_equity > 0:
                    roe = net_income / avg_equity * 100
                    logger.info(
                        f"{stock_code}: 예상ROE={roe:.2f}% "
                        f"(순이익={net_income:,.0f}, 평균자기자본={avg_equity:,.0f})"
                    )
                    return round(roe, 2)
        logger.warning(f"{stock_code}: 예상 ROE를 계산할 수 없습니다.")
        return 0.0

    # ── 단일 종목 수집 ─────────────────────────────────────────────────────────

    def fetch(self, stock_code: str) -> dict:
        """종목코드로 FnGuide Snapshot 페이지와 재무 API 조회 후 재무 기초 데이터 반환"""
        soup = self.get_page(stock_code)
        dataset = self.get_financial(stock_code)
        if soup is None or not dataset:
            return {'종목코드': stock_code, '자본총계(원)': 0.0, '총주식수': 0, '예상ROE(%)': 0.0}

        equity = self.find_equity_from_financial(dataset, stock_code)
        issued = self.find_issued_shares(soup)
        treasury = self.find_treasury_shares(soup)
        future_roe = self.find_future_roe_from_financial(dataset, stock_code)

        return {
            '종목코드': stock_code,
            '자본총계(원)': equity,
            '총주식수': issued - treasury,
            '예상ROE(%)': future_roe,
        }

    # ── 전체 종목 수집 ─────────────────────────────────────────────────────────

    def fetch_all(self, stock_codes: list) -> pd.DataFrame:
        """종목 리스트 전체 조회, DataFrame 반환"""
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.fetch, code): code for code in stock_codes}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    code = futures[future]
                    logger.error(f"{code} 수집 실패: {e}")
        return pd.DataFrame(results)

    def save(self, df: pd.DataFrame, filename: str):
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"재무 데이터 저장: {filename}")

    def run_from_roe_csv(self, roe_csv: str, output_csv: str):
        """ROE CSV에서 종목코드를 읽어 재무 데이터를 수집하고 output CSV에 저장"""
        roe_df = pd.read_csv(roe_csv, encoding='utf-8-sig', dtype={'종목코드': str})
        roe_df['종목코드'] = roe_df['종목코드'].str.zfill(6)
        codes = roe_df['종목코드'].tolist()
        logger.info(f"ROE CSV에서 {len(codes)}개 종목코드 읽음: {roe_csv}")

        df = self.fetch_all(codes)
        self.save(df, output_csv)
        logger.info(f"재무 데이터 수집 완료 → {output_csv}")
        return df


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='FnGuide 재무 데이터 수집')
    parser.add_argument('--roe-csv', required=True, help='ROE 결과 CSV (종목코드 소스)')
    parser.add_argument('--output', required=True, help='저장할 재무 데이터 CSV 경로')
    parser.add_argument('--workers', type=int, default=5, help='병렬 처리 워커 수')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    fetcher = StockFundamentalsFetcher(max_workers=args.workers)
    df = fetcher.run_from_roe_csv(args.roe_csv, args.output)
    print(df.to_string(index=False))
