import pytest
import pandas as pd
from unittest.mock import MagicMock
from roe_high_performers_full import ROEHighPerformersFull


def make_mock_analyzer(roe_data: dict, target_period="2025/12(E)", target_year=2025):
    """ROE 데이터를 반환하는 mock analyzer 생성"""
    mock = MagicMock()
    mock.target_period = target_period
    mock.target_year = target_year
    roe_col = f"{target_period}_ROE(%)"
    rows = [
        {"종목코드": code, "종목명": name, "시장": "KOSPI", roe_col: roe}
        for code, name, roe in roe_data
    ]
    mock.analyze_stocks_roe_dynamic.return_value = pd.DataFrame(rows)
    return mock


def make_finder(roe_data, threshold=10.0):
    mock = make_mock_analyzer(roe_data)
    return ROEHighPerformersFull(roe_threshold=threshold, analyzer=mock)


# ── 테스트 1: 임계값 이상만 반환 ─────────────────────────────────────────────

def test_find_high_roe_stocks_returns_only_stocks_above_threshold():
    finder = make_finder([
        ("005930", "삼성전자", 12.5),
        ("000660", "SK하이닉스", 8.0),   # 임계값 미달
        ("035420", "NAVER", 15.3),
    ], threshold=10.0)

    result = finder.find_high_roe_stocks()

    codes = result["종목코드"].tolist()
    assert "005930" in codes
    assert "035420" in codes
    assert "000660" not in codes


def test_find_high_roe_stocks_returns_sorted_by_roe_descending():
    finder = make_finder([
        ("000660", "SK하이닉스", 11.0),
        ("035420", "NAVER", 25.0),
        ("005930", "삼성전자", 17.5),
    ], threshold=10.0)

    result = finder.find_high_roe_stocks()

    roe_col = "2025/12(E)_ROE(%)"
    roe_values = result[roe_col].tolist()
    assert roe_values == sorted(roe_values, reverse=True)
