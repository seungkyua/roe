import pytest
import pandas as pd
from s_rim import SRIMCalculator
from s_rim_pipeline import merge_inputs, SRIMPipeline


# ── SRIMCalculator ────────────────────────────────────────────────────────────

def make_calc(discount_rate=9.24):
    return SRIMCalculator(discount_rate=discount_rate)


def test_proper_price_returns_srim_valuation():
    """기본 S-RIM: V = equity + equity*(ROE-r)/r, price = V / total_shares"""
    calc = make_calc(discount_rate=9.24)
    equity = 126_800_000_000
    roe = 31.95
    total_shares = 89_968_897 - 3_793

    price = calc.proper_price(equity, roe, total_shares)

    # cal_proper_values 직접 계산값과 일치해야 함
    from s_rim import cal_proper_values
    _, expected = cal_proper_values(9.24, equity, roe, total_shares)
    assert price == expected


def test_conservative_price_returns_supernormal_valuation():
    """초과이익 10% 감소 모델로 보수적 주가 반환"""
    calc = make_calc(discount_rate=9.24)
    equity = 126_800_000_000
    roe = 31.95
    total_shares = 89_968_897 - 3_793

    price = calc.conservative_price(equity, roe, total_shares)

    from s_rim import cal_supernormal_values
    expected = cal_supernormal_values(9.24, equity, roe, total_shares)
    assert price == expected


def test_calc_row_adds_both_prices_to_dict():
    """calc_row()가 입력 dict에 적정주가와 보수적주가를 추가한 dict를 반환"""
    calc = make_calc(discount_rate=9.24)
    row = {
        '종목코드': '071280',
        '종목명': '원텍',
        '시장': 'KOSDAQ',
        'ROE(%)': 31.95,
        '자본총계(원)': 126_800_000_000,
        '총주식수': 89_968_897 - 3_793,
    }

    result = calc.calc_row(row)

    assert '적정주가(S-RIM)' in result
    assert '보수적주가(S-RIM)' in result
    assert result['적정주가(S-RIM)'] == calc.proper_price(row['자본총계(원)'], row['ROE(%)'], row['총주식수'])
    assert result['보수적주가(S-RIM)'] == calc.conservative_price(row['자본총계(원)'], row['ROE(%)'], row['총주식수'])
    assert result['종목코드'] == '071280'


# ── merge_inputs ──────────────────────────────────────────────────────────────

def make_roe_df(rows):
    return pd.DataFrame([
        {'종목코드': code, '종목명': name, '2026/12(E)_ROE(%)': roe}
        for code, name, roe in rows
    ])

def make_fundamentals_df(rows):
    return pd.DataFrame([
        {'종목코드': code, '자본총계(원)': equity, '총주식수': shares}
        for code, equity, shares in rows
    ])


def test_merge_inputs_joins_on_stock_code():
    """두 DataFrame이 종목코드 기준으로 병합된다"""
    roe_df = make_roe_df([('005930', '삼성전자', 12.5), ('035420', 'NAVER', 7.2)])
    fundamentals_df = make_fundamentals_df([('005930', 300_000_000_000, 5_000_000)])

    merged = merge_inputs(roe_df, fundamentals_df)

    assert len(merged) == 1
    assert merged.iloc[0]['종목코드'] == '005930'
    assert '2026/12(E)_ROE(%)' in merged.columns
    assert '자본총계(원)' in merged.columns


def test_merge_inputs_excludes_unmatched_stocks():
    """한쪽에만 있는 종목은 결과에서 제외된다"""
    roe_df = make_roe_df([('005930', '삼성전자', 12.5), ('000660', 'SK하이닉스', 20.0)])
    fundamentals_df = make_fundamentals_df([('000660', 200_000_000_000, 7_000_000)])

    merged = merge_inputs(roe_df, fundamentals_df)

    codes = merged['종목코드'].tolist()
    assert '000660' in codes
    assert '005930' not in codes


# ── SRIMPipeline.run() ────────────────────────────────────────────────────────

def test_load_normalizes_roe_column_name(tmp_path):
    """ROE CSV의 YYYY/12(E)_ROE(%) 컬럼이 ROE(%)로 정규화된다"""
    roe_csv = tmp_path / "roe.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"

    pd.DataFrame([
        {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI', '2026/12(E)_ROE(%)': 10.85},
    ]).to_csv(roe_csv, index=False, encoding='utf-8-sig')

    pd.DataFrame([
        {'종목코드': '005930', '자본총계(원)': 4_243_133 * 1e8, '총주식수': 5_764_191_903},
    ]).to_csv(fundamentals_csv, index=False, encoding='utf-8-sig')

    pipeline = SRIMPipeline(9.24, str(roe_csv), str(fundamentals_csv))
    merged = pipeline.load()

    assert 'ROE(%)' in merged.columns
    assert '2026/12(E)_ROE(%)' not in merged.columns
    assert merged.iloc[0]['ROE(%)'] == pytest.approx(10.85)


def test_pipeline_run_applies_srim_to_merged_data(tmp_path):
    """run()이 병합 데이터 전체에 S-RIM 계산을 적용한 DataFrame을 반환한다"""
    roe_csv = tmp_path / "roe.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"

    pd.DataFrame([
        {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI', 'ROE(%)': 12.5},
        {'종목코드': '035420', '종목명': 'NAVER', '시장': 'KOSPI', 'ROE(%)': 7.2},
    ]).to_csv(roe_csv, index=False, encoding='utf-8-sig')

    pd.DataFrame([
        {'종목코드': '005930', '자본총계(원)': 300_000_000_000, '총주식수': 5_000_000},
    ]).to_csv(fundamentals_csv, index=False, encoding='utf-8-sig')

    pipeline = SRIMPipeline(
        discount_rate=9.24,
        roe_csv=str(roe_csv),
        fundamentals_csv=str(fundamentals_csv),
    )
    result = pipeline.run()

    assert len(result) == 1
    assert result.iloc[0]['종목코드'] == '005930'
    assert '적정주가(S-RIM)' in result.columns
    assert '보수적주가(S-RIM)' in result.columns
    assert result.iloc[0]['적정주가(S-RIM)'] > 0
