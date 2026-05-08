import pytest
import pandas as pd
from stock_lookup import find_stock, build_display_row


SAMPLE_DF = pd.DataFrame([
    {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI',
     'ROE(%)': 10.85, '예상ROE(%)': 29.42,
     '적정주가(S-RIM)': 76_720, '보수적주가(S-RIM)': 75_040,
     '예상적정주가(S-RIM)': 208_040, '예상보수적주가(S-RIM)': 135_320},
    {'종목코드': '035420', '종목명': 'NAVER', '시장': 'KOSPI',
     'ROE(%)': 7.2, '예상ROE(%)': 0.0,
     '적정주가(S-RIM)': 90_000, '보수적주가(S-RIM)': 80_000,
     '예상적정주가(S-RIM)': 0, '예상보수적주가(S-RIM)': 0},
    {'종목코드': '000660', '종목명': 'SK하이닉스', '시장': 'KOSPI',
     'ROE(%)': 44.15, '예상ROE(%)': 38.27,
     '적정주가(S-RIM)': 740_490, '보수적주가(S-RIM)': 434_150,
     '예상적정주가(S-RIM)': 620_000, '예상보수적주가(S-RIM)': 380_000},
])


# ── find_stock ────────────────────────────────────────────────────────────────

def test_find_stock_by_exact_code():
    row = find_stock(SAMPLE_DF, '005930')
    assert row is not None
    assert row['종목명'] == '삼성전자'


def test_find_stock_by_partial_name():
    row = find_stock(SAMPLE_DF, '삼성')
    assert row is not None
    assert row['종목코드'] == '005930'


def test_find_stock_by_partial_name_case_insensitive():
    row = find_stock(SAMPLE_DF, 'naver')
    assert row is not None
    assert row['종목코드'] == '035420'


def test_find_stock_returns_none_when_not_found():
    row = find_stock(SAMPLE_DF, '없는종목')
    assert row is None


# ── build_display_row ─────────────────────────────────────────────────────────

def test_build_display_row_includes_current_price_and_upside():
    row = SAMPLE_DF.iloc[0].to_dict()
    current_price = 268_500

    display = build_display_row(row, current_price)

    assert display['현재가'] == 268_500
    expected_pct = (208_040 - 268_500) / 268_500 * 100
    assert display['상승여력(%)'] == pytest.approx(expected_pct, rel=1e-3)


def test_build_display_row_sets_zero_upside_when_no_expected_roe():
    row = SAMPLE_DF.iloc[1].to_dict()  # NAVER: 예상적정주가=0

    display = build_display_row(row, current_price=80_000)

    assert display['상승여력(%)'] == 0.0


def test_build_display_row_contains_all_required_columns():
    row = SAMPLE_DF.iloc[0].to_dict()
    display = build_display_row(row, current_price=268_500)

    required = [
        '종목코드', '종목명', '시장',
        'ROE(%)', '예상ROE(%)',
        '현재가',
        '적정주가(S-RIM)', '보수적주가(S-RIM)',
        '예상적정주가(S-RIM)', '예상보수적주가(S-RIM)',
        '상승여력(%)',
    ]
    for col in required:
        assert col in display, f"'{col}' 컬럼이 없음"
