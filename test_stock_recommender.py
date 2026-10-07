import pytest
import pandas as pd
from unittest.mock import MagicMock
from stock_recommender import fetch_current_price, StockRecommender, sort_results, SORT_MODES


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def make_srim_df(rows):
    return pd.DataFrame(rows)


# ── 테스트 1: 현재가 파싱 ────────────────────────────────────────────────────

def make_price_api_session(code: str, close_price: str = None, status_error: bool = False):
    """네이버 증권 종목 기본정보 API 응답 모킹 (해당 URL 이 아니면 구버전 빈 페이지 반환)"""
    session = MagicMock()

    def fake_get(url, timeout=None):
        resp = MagicMock(text="<html></html>")
        if url == f"https://m.stock.naver.com/api/stock/{code}/basic":
            if status_error:
                resp.raise_for_status.side_effect = Exception("409 Client Error")
            resp.json.return_value = {"itemCode": code, "closePrice": close_price}
        return resp

    session.get.side_effect = fake_get
    return session


def test_shouldReturnPriceWhenNaverStockApiResponds():
    # API 레벨: 네이버 증권 API 의 closePrice('14,980')를 정수로 반환한다
    session = make_price_api_session("097230", close_price="14,980")

    assert fetch_current_price("097230", session) == 14_980


def test_shouldReturnZeroWhenNaverStockApiReturnsError():
    # 존재하지 않는 종목코드는 409 오류가 오므로 0 을 반환한다
    session = make_price_api_session("000000", status_error=True)

    assert fetch_current_price("000000", session) == 0


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


# ── sort_results ──────────────────────────────────────────────────────────────

def make_sort_df():
    return pd.DataFrame([
        {'종목코드': 'A', '종목명': 'α', '시장': 'KOSPI',
         '적정주가(S-RIM)': 100_000, '예상적정주가(S-RIM)': 150_000, '현재가': 80_000},
        {'종목코드': 'B', '종목명': 'β', '시장': 'KOSPI',
         '적정주가(S-RIM)': 50_000,  '예상적정주가(S-RIM)': 200_000, '현재가': 90_000},
        {'종목코드': 'C', '종목명': 'γ', '시장': 'KOSPI',
         '적정주가(S-RIM)': 200_000, '예상적정주가(S-RIM)': 180_000, '현재가': 70_000},
    ])


def test_sort_results_proper_sorts_by_proper_price_vs_current():
    """'proper': (적정주가 - 현재가) / 현재가 * 100 내림차순. C 1위(+185.7%)"""
    result = sort_results(make_sort_df(), mode='proper')
    assert result.iloc[0]['종목코드'] == 'C'
    assert '정렬기준(%)' in result.columns


def test_sort_results_expected_sorts_by_expected_price_vs_current():
    """'expected': (예상적정주가 - 현재가) / 현재가 * 100 내림차순. C 1위(+157.1%)"""
    result = sort_results(make_sort_df(), mode='expected')
    assert result.iloc[0]['종목코드'] == 'C'
    assert '정렬기준(%)' in result.columns


def test_sort_results_growth_sorts_by_expected_vs_proper():
    """'growth': (예상적정주가 - 적정주가) / 적정주가 * 100 내림차순. B 1위(+300%)"""
    result = sort_results(make_sort_df(), mode='growth')
    assert result.iloc[0]['종목코드'] == 'B'
    assert '정렬기준(%)' in result.columns


def test_sort_results_excludes_rows_with_zero_denominator():
    """분모가 0인 행은 결과에서 제외한다"""
    df = make_sort_df().copy()
    df.loc[0, '현재가'] = 0  # A: 현재가=0 → proper/expected 정렬 시 제외

    result = sort_results(df, mode='proper')

    assert 'A' not in result['종목코드'].tolist()


def test_sort_results_raises_on_invalid_mode():
    """유효하지 않은 mode는 ValueError를 발생시킨다"""
    with pytest.raises(ValueError, match='mode'):
        sort_results(make_sort_df(), mode='invalid')


def test_sort_results_growth_does_not_need_current_price():
    """'growth' 모드는 현재가 컬럼 없이도 동작한다"""
    df = make_sort_df().drop(columns=['현재가'])
    result = sort_results(df, mode='growth')
    assert len(result) > 0
    assert result.iloc[0]['종목코드'] == 'B'


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
