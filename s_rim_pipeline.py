#!/usr/bin/env python3
"""
S-RIM 파이프라인: ROE CSV + 재무 데이터 CSV → 적정 주가 계산
"""

import argparse
import pandas as pd
from s_rim import SRIMCalculator


def merge_inputs(roe_df: pd.DataFrame, fundamentals_df: pd.DataFrame) -> pd.DataFrame:
    """두 DataFrame을 종목코드 기준 inner join으로 병합"""
    return pd.merge(roe_df, fundamentals_df, on='종목코드', how='inner')


class SRIMPipeline:
    def __init__(self, discount_rate: float, roe_csv: str, fundamentals_csv: str):
        self.discount_rate = discount_rate
        self.roe_csv = roe_csv
        self.fundamentals_csv = fundamentals_csv
        self.calculator = SRIMCalculator(discount_rate)

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
        return pd.DataFrame(results)

    def save(self, results: pd.DataFrame, filename: str):
        results.to_csv(filename, index=False, encoding='utf-8-sig')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='S-RIM 적정 주가 계산 파이프라인')
    parser.add_argument('--roe-csv', required=True)
    parser.add_argument('--fundamentals-csv', required=True)
    parser.add_argument('--discount-rate', type=float, default=9.24)
    args = parser.parse_args()

    pipeline = SRIMPipeline(args.discount_rate, args.roe_csv, args.fundamentals_csv)
    results = pipeline.run()
    out = f"srim_results_{args.discount_rate}.csv"
    pipeline.save(results, out)
    print(results.to_string(index=False))
    print(f"\n결과 저장: {out}")
