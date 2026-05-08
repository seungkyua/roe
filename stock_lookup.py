#!/usr/bin/env python3
"""
종목 코드 또는 종목명으로 S-RIM 적정 주가 조회
stock_recommender.py 의 fetch_current_price() 를 재사용

사용 예:
  python stock_lookup.py 005930
  python stock_lookup.py 삼성전자
  python stock_lookup.py 삼성  --srim-csv srim_results_10.41.csv
"""

import argparse
import glob
import os
import sys
import pandas as pd
from stock_recommender import fetch_current_price

DISPLAY_COLUMNS = [
    '종목코드', '종목명', '시장',
    'ROE(%)', '예상ROE(%)',
    '현재가',
    '적정주가(S-RIM)', '보수적주가(S-RIM)',
    '예상적정주가(S-RIM)', '예상보수적주가(S-RIM)',
    '상승여력(%)',
]


def find_latest_srim_csv() -> str:
    """srim_results_*.csv 중 가장 최신 파일 반환"""
    files = glob.glob('srim_results_*.csv')
    if not files:
        raise FileNotFoundError("srim_results_*.csv 파일을 찾을 수 없습니다.")
    return max(files, key=os.path.getmtime)


def load_srim(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding='utf-8-sig', dtype={'종목코드': str})
    df['종목코드'] = df['종목코드'].str.zfill(6)
    return df


def find_stock(df: pd.DataFrame, query: str) -> dict | None:
    """
    종목코드(정확 일치) 또는 종목명(부분 일치, 대소문자 무시)으로 검색.
    첫 번째 일치 행을 dict로 반환. 없으면 None.
    """
    # 6자리 숫자면 코드로 검색
    normalized = query.strip().zfill(6) if query.strip().isdigit() else None
    if normalized:
        matched = df[df['종목코드'] == normalized]
    else:
        matched = df[df['종목명'].str.contains(query.strip(), case=False, na=False)]

    if matched.empty:
        return None
    return matched.iloc[0].to_dict()


def build_display_row(row: dict, current_price: int) -> dict:
    """
    row 에 현재가와 상승여력(%)을 추가한 dict 반환.
    예상적정주가(S-RIM) = 0 이면 상승여력(%) = 0.0.
    """
    expected_price = row.get('예상적정주가(S-RIM)', 0) or 0

    if expected_price > 0 and current_price > 0:
        upside_pct = round((expected_price - current_price) / current_price * 100, 2)
    else:
        upside_pct = 0.0

    return {
        **row,
        '현재가': current_price,
        '상승여력(%)': upside_pct,
    }


def print_result(display: dict) -> None:
    cols = [c for c in DISPLAY_COLUMNS if c in display]
    width = max(len(c) for c in cols) + 2

    print()
    print("=" * 60)
    for col in cols:
        val = display[col]
        if isinstance(val, float):
            if col in ('ROE(%)', '예상ROE(%)', '상승여력(%)'):
                formatted = f"{val:.2f}%"
            elif col in ('자본총계(원)',):
                formatted = f"{val:.2e}"
            else:
                formatted = f"{int(val):,}" if val == int(val) else f"{val:,.2f}"
        elif isinstance(val, int):
            formatted = f"{val:,}"
        else:
            formatted = str(val)
        print(f"  {col:<{width}}: {formatted}")
    print("=" * 60)
    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='종목 S-RIM 적정 주가 조회')
    parser.add_argument('query', help='종목코드 또는 종목명 (부분 일치 가능)')
    parser.add_argument('--srim-csv', default=None,
                        help='S-RIM 결과 CSV 경로 (기본값: 최신 srim_results_*.csv)')
    args = parser.parse_args()

    csv_path = args.srim_csv or find_latest_srim_csv()
    df = load_srim(csv_path)

    row = find_stock(df, args.query)
    if row is None:
        print(f"'{args.query}' 에 해당하는 종목을 찾을 수 없습니다.")
        sys.exit(1)

    print(f"종목 조회: {row['종목명']} ({row['종목코드']})")
    print("현재가 조회 중...")
    current_price = fetch_current_price(row['종목코드'])
    display = build_display_row(row, current_price)
    print_result(display)
