#!/usr/bin/env python3
"""
FnGuide에서 종목별 자본총계(지배주주지분)와 총주식수를 수집
URL: https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp?pGB=1&gicode=A{code}&...
"""

import re
import time
import logging
import warnings
import urllib3
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings('ignore', message='.*OpenSSL.*')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

FNGUIDE_URL = (
    "https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp"
    "?pGB=1&gicode=A{code}&cID=&MenuYn=Y&ReportGB=&NewMenuID=11&stkGb=701"
)


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
        url = FNGUIDE_URL.format(code=stock_code)
        for attempt in range(3):
            try:
                resp = self.session.get(url, timeout=15)
                resp.raise_for_status()
                resp.encoding = 'utf-8'
                return BeautifulSoup(resp.text, 'html.parser')
            except Exception as e:
                logger.warning(f"{stock_code} 페이지 로드 실패 (시도 {attempt+1}/3): {e}")
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
        return None

    # ── 파싱 메서드 ────────────────────────────────────────────────────────────

    def find_equity(self, soup, stock_code: str) -> float:
        """
        Financial Highlight 표(IFRS연결 Annual+Net Quarter)에서
        작년 12월(current_year-1 / 12) 지배주주지분을 억원 → 원으로 변환하여 반환.

        FnGuide 테이블 구조:
          rows[0]: IFRS(연결) | Annual | Net Quarter  (섹션 헤더)
          rows[1]: 2023/12 | 2024/12 | 2025/12 | ...  (연도 헤더, 레이블 셀 없음)
          data rows: 항목명 | 값1 | 값2 | ...  (셀[0]=항목, 셀[1+]=연도별 값)
          → 연도 헤더 index i → 데이터 셀 index i+1
        """
        last_year = self.current_year - 1
        target_col_text = f"{last_year}/12"

        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if len(rows) < 3:
                continue

            header_texts = [c.get_text(strip=True) for c in rows[0].find_all(['td', 'th'])]
            if 'IFRS(연결)' not in header_texts or 'Annual' not in header_texts:
                continue

            # 연도 헤더 행 (rows[1]): 레이블 셀 없이 연도만 나열
            year_cells = [c.get_text(strip=True) for c in rows[1].find_all(['td', 'th'])]
            try:
                year_idx = year_cells.index(target_col_text)
            except ValueError:
                continue

            # 데이터 행은 셀[0]이 항목명이므로 +1 오프셋
            data_col_idx = year_idx + 1

            for row in rows[2:]:
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                if cells[0].get_text(strip=True) == '지배주주지분':
                    if len(cells) > data_col_idx:
                        val_str = cells[data_col_idx].get_text(strip=True).replace(',', '')
                        if val_str and re.match(r'^-?\d+(\.\d+)?$', val_str):
                            return float(val_str) * 1e8  # 억원 → 원
            break  # 테이블 찾았으면 루프 종료

        logger.warning(f"{stock_code}: 지배주주지분 값을 찾지 못했습니다.")
        return 0.0

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
        """주주구분 현황 표에서 자기주식(자사주+자사주신탁) 보통주 반환"""
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if not cells:
                    continue
                if '자기주식' in cells[0].get_text(strip=True) and len(cells) > 2:
                    val = cells[2].get_text(strip=True).replace(',', '')
                    if val.isdigit():
                        return int(val)
        logger.warning("자기주식을 찾지 못했습니다.")
        return 0

    # ── 단일 종목 수집 ─────────────────────────────────────────────────────────

    def fetch(self, stock_code: str) -> dict:
        """종목코드로 FnGuide 페이지 조회 후 재무 기초 데이터 반환"""
        soup = self.get_page(stock_code)
        if soup is None:
            return {'종목코드': stock_code, '자본총계(원)': 0.0, '총주식수': 0}

        equity = self.find_equity(soup, stock_code)
        issued = self.find_issued_shares(soup)
        treasury = self.find_treasury_shares(soup)

        return {
            '종목코드': stock_code,
            '자본총계(원)': equity,
            '총주식수': issued - treasury,
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
