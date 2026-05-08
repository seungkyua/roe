import pytest
import pandas as pd
from bs4 import BeautifulSoup
from unittest.mock import MagicMock
from stock_recommender import fetch_current_price, StockRecommender


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def make_naver_price_soup(price: int) -> BeautifulSoup:
    """Naver Finance 현재가 페이지 구조 모킹"""
    html = f"""<html><body>
    <p class="no_today">
      <span class="blind">{price:,}</span>
    </p>
    </body></html>"""
    return BeautifulSoup(html, 'html.parser')


def make_srim_df(rows):
    return pd.DataFrame(rows)


# ── 테스트 1: 현재가 파싱 ────────────────────────────────────────────────────

def test_fetch_current_price_parses_price_from_naver_page(monkeypatch):
    """Naver Finance 페이지에서 현재가를 정수로 반환한다"""
    mock_soup = make_naver_price_soup(268_500)
    monkeypatch.setattr('stock_recommender._get_naver_price_page', lambda code, session: mock_soup)

    price = fetch_current_price('005930')

    assert price == 268_500


def test_fetch_current_price_returns_zero_on_failure(monkeypatch):
    """페이지 조회 실패 시 0을 반환한다"""
    monkeypatch.setattr('stock_recommender._get_naver_price_page', lambda code, session: None)

    price = fetch_current_price('000000')

    assert price == 0


# ── 테스트 2: upside 계산 ────────────────────────────────────────────────────

def test_recommender_calculates_upside_percentage():
    """상승여력(%) = (예상적정주가 - 현재가) / 현재가 * 100"""
    rec = StockRecommender.__new__(StockRecommender)
    df = make_srim_df([
        {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI',
         'ROE(%)': 10.85, '예상ROE(%)': 29.42, '현재가': 268_500,
         '적정주가(S-RIM)': 76_720, '보수적주가(S-RIM)': 75_040,
         '예상적정주가(S-RIM)': 537_000, '예상보수적주가(S-RIM)': 135_320},
    ])

    result = rec.calculate_upside(df)

    expected_pct = (537_000 - 268_500) / 268_500 * 100
    assert result.iloc[0]['상승여력(%)'] == pytest.approx(expected_pct, rel=1e-3)


def test_recommender_sorts_by_upside_percentage_not_absolute():
    """절대값이 아닌 % 기준으로 정렬한다 (절대값 순서와 다른 케이스)"""
    rec = StockRecommender.__new__(StockRecommender)
    df = make_srim_df([
        # A: 절대차 크지만 % 작음 — 현재가 100,000에 예상적정 150,000 → +50%
        {'종목코드': 'A', '종목명': '절대값큰종목', '시장': 'KOSPI',
         'ROE(%)': 10.0, '예상ROE(%)': 20.0, '현재가': 100_000,
         '적정주가(S-RIM)': 90_000, '보수적주가(S-RIM)': 80_000,
         '예상적정주가(S-RIM)': 150_000, '예상보수적주가(S-RIM)': 120_000},
        # B: 절대차 작지만 % 큼 — 현재가 5,000에 예상적정 20,000 → +300%
        {'종목코드': 'B', '종목명': '퍼센트큰종목', '시장': 'KOSPI',
         'ROE(%)': 15.0, '예상ROE(%)': 30.0, '현재가': 5_000,
         '적정주가(S-RIM)': 6_000, '보수적주가(S-RIM)': 5_500,
         '예상적정주가(S-RIM)': 20_000, '예상보수적주가(S-RIM)': 15_000},
    ])

    result = rec.calculate_upside(df)

    # B가 먼저 와야 함 (절대차: A=50,000 > B=15,000이지만 %: B=300% > A=50%)
    assert result.iloc[0]['종목코드'] == 'B'
    assert result.iloc[1]['종목코드'] == 'A'


def test_recommender_excludes_stocks_with_no_expected_roe():
    """예상ROE(%)가 0인 종목(예상적정주가=0)은 결과에서 제외한다"""
    rec = StockRecommender.__new__(StockRecommender)
    df = make_srim_df([
        {'종목코드': 'A', '종목명': '예상ROE있음', '시장': 'KOSPI',
         'ROE(%)': 10.0, '예상ROE(%)': 20.0, '현재가': 5_000,
         '적정주가(S-RIM)': 6_000, '보수적주가(S-RIM)': 5_500,
         '예상적정주가(S-RIM)': 15_000, '예상보수적주가(S-RIM)': 12_000},
        {'종목코드': 'B', '종목명': '예상ROE없음', '시장': 'KOSPI',
         'ROE(%)': 10.0, '예상ROE(%)': 0.0, '현재가': 5_000,
         '적정주가(S-RIM)': 6_000, '보수적주가(S-RIM)': 5_500,
         '예상적정주가(S-RIM)': 0, '예상보수적주가(S-RIM)': 0},
    ])

    result = rec.calculate_upside(df)

    assert len(result) == 1
    assert result.iloc[0]['종목코드'] == 'A'
