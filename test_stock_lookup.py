import pytest
import pandas as pd
from bs4 import BeautifulSoup
from stock_lookup import resolve_code, fetch_price_from_api, build_result


# ── resolve_code ──────────────────────────────────────────────────────────────

def test_resolve_code_returns_code_directly_for_6digit_input():
    """6자리 숫자는 종목코드로 그대로 반환한다"""
    code = resolve_code('005930')
    assert code == '005930'


def test_resolve_code_zeropads_short_numeric_input():
    """숫자이지만 6자리 미만이면 제로패딩한다"""
    code = resolve_code('5930')
    assert code == '005930'


def test_resolve_code_searches_by_name_when_text_given(monkeypatch):
    """종목명이 주어지면 SISE 검색으로 코드를 반환한다"""
    monkeypatch.setattr('stock_lookup._search_code_by_name', lambda name: '071050')
    code = resolve_code('한국금융지주')
    assert code == '071050'


def test_resolve_code_raises_when_name_not_found(monkeypatch):
    """종목명 검색 실패 시 ValueError를 발생시킨다"""
    monkeypatch.setattr('stock_lookup._search_code_by_name', lambda name: None)
    with pytest.raises(ValueError, match='찾을 수 없습니다'):
        resolve_code('없는종목')


# ── fetch_price_from_api ──────────────────────────────────────────────────────

def test_fetch_price_from_api_returns_close_price(monkeypatch):
    """Naver polling API에서 종가(closePrice)를 int로 반환한다"""
    import stock_lookup
    mock_data = {'datas': [{'closePrice': '268,500'}]}
    monkeypatch.setattr(stock_lookup, '_call_polling_api', lambda code: mock_data)

    price = fetch_price_from_api('005930')

    assert price == 268_500


def test_fetch_price_from_api_returns_zero_on_failure(monkeypatch):
    """API 호출 실패 시 0을 반환한다"""
    import stock_lookup
    monkeypatch.setattr(stock_lookup, '_call_polling_api', lambda code: None)

    price = fetch_price_from_api('000000')

    assert price == 0


# ── build_result ──────────────────────────────────────────────────────────────

def test_build_result_contains_all_required_columns():
    """build_result()가 필수 컬럼을 모두 포함한 dict를 반환한다"""
    result = build_result(
        code='005930', name='삼성전자', market='KOSPI',
        current_roe=10.85, future_roe=29.42,
        equity=424_313_300_000_000, total_shares=5_764_191_903,
        discount_rate=10.41,
        current_price=268_500,
    )

    required = [
        '종목코드', '종목명', '시장',
        'ROE(%)', '예상ROE(%)',
        '현재가',
        '적정주가(S-RIM)', '보수적주가(S-RIM)',
        '예상적정주가(S-RIM)', '예상보수적주가(S-RIM)',
        '상승여력(%)',
    ]
    for col in required:
        assert col in result, f"'{col}' 컬럼 없음"


def test_build_result_calculates_upside_percentage():
    """상승여력(%) = (예상적정주가 - 현재가) / 현재가 * 100"""
    result = build_result(
        code='005930', name='삼성전자', market='KOSPI',
        current_roe=10.85, future_roe=29.42,
        equity=424_313_300_000_000, total_shares=5_764_191_903,
        discount_rate=10.41,
        current_price=268_500,
    )

    expected_price = result['예상적정주가(S-RIM)']
    expected_pct = (expected_price - 268_500) / 268_500 * 100
    assert result['상승여력(%)'] == pytest.approx(expected_pct, rel=1e-3)


def test_build_result_sets_zero_upside_when_future_roe_is_zero():
    """예상ROE가 0이면 예상 주가와 상승여력도 0이다"""
    result = build_result(
        code='035420', name='NAVER', market='KOSPI',
        current_roe=7.2, future_roe=0.0,
        equity=100_000_000_000, total_shares=10_000_000,
        discount_rate=10.41,
        current_price=80_000,
    )

    assert result['예상적정주가(S-RIM)'] == 0
    assert result['상승여력(%)'] == 0.0
