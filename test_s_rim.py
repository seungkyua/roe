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
