import importlib
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from stock_roe_analyzer_final import StockROEAnalyzerFinal


def make_analyzer(year=2025):
    analyzer = StockROEAnalyzerFinal.__new__(StockROEAnalyzerFinal)
    analyzer.target_year = year
    analyzer.target_period = f"{year}/12(E)"
    return analyzer


# ── 테스트 1: 헤더에서 target_year 컬럼 인덱스 탐색 ──────────────────────────

def test_find_target_year_column_returns_correct_index():
    analyzer = make_analyzer(year=2025)
    header_cells = ["IFRS(연결)", "2023/12", "2024/12", "2025/12(E)", "2026/12(E)"]
    idx = analyzer.find_target_year_column(header_cells)
    assert idx == 3


def test_find_target_year_column_returns_none_when_not_found():
    analyzer = make_analyzer(year=2025)
    header_cells = ["IFRS(연결)", "2023/12", "2024/12"]
    idx = analyzer.find_target_year_column(header_cells)
    assert idx is None


def test_find_target_year_column_selects_only_matching_year():
    analyzer = make_analyzer(year=2026)
    header_cells = ["IFRS(연결)", "2024/12", "2025/12(E)", "2026/12(E)", "2027/12(E)"]
    idx = analyzer.find_target_year_column(header_cells)
    assert idx == 3


def test_shouldLoadStockListWhenStockListModuleIsRenamedWithNumberPrefix():
    # 종목 리스트 모듈 파일명이 01_stock_list_manual.py 여도 정상적으로 불러와야 한다
    analyzer = make_analyzer()
    expected = pd.DataFrame([{"종목코드": "005930", "종목명": "삼성전자", "시장": "KOSPI"}])
    stock_list_manual = importlib.import_module("01_stock_list_manual")
    with patch.object(stock_list_manual, "get_stock_list", return_value=expected):
        result = analyzer.get_stock_list()
    assert result is expected


def make_financial_dataset(yymm_list, roe_values):
    """FnGuide getSnpFinancial API 응답(dataset) 모킹: 연도 헤더 + ROE 행"""
    header = [{"YYMM": yymm, "CD": f"VAL{i}"} for i, yymm in enumerate(yymm_list, 1)]
    roe_row = {"NAME": "ROE", **{f"VAL{i}": v for i, v in enumerate(roe_values, 1)}}
    sales_row = {"NAME": "매출액", **{f"VAL{i}": "100.00" for i in range(1, len(yymm_list) + 1)}}
    return {"header": header, "data": [sales_row, roe_row]}


def make_api_response(dataset=None, json_error=False):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    if json_error:
        resp.json.side_effect = ValueError("Expecting value")
    else:
        resp.json.return_value = {"dataset": dataset}
    return resp


def test_shouldReturnRoeWhenFnguideFinancialApiResponds():
    # API 레벨: FnGuide 신버전 재무 API 응답에서 목표 연도 ROE 를 추출한다
    analyzer = make_analyzer(2026)
    analyzer.session = MagicMock()
    analyzer.session.get.return_value = make_api_response(make_financial_dataset(
        ["2023/12", "2024/12", "2025/12", "2026/12", "2025/12", "2026/03", "2026/06", "2026/09"],
        ["5.00", "9.00", "10.85", "55.22", "10.85", "12.00", "13.00", None],
    ))

    result = analyzer.analyze_single_stock({"종목코드": "005930", "종목명": "삼성전자", "시장": "KOSPI"})

    assert result["2026/12(E)_ROE(%)"] == 55.22


def test_shouldReturnZeroRoeWhenApiResponseIsNotJson():
    # ETF 등 재무 데이터가 없는 종목은 빈 응답이 오므로 ROE 0.0 으로 처리한다
    analyzer = make_analyzer(2026)
    analyzer.session = MagicMock()
    analyzer.session.get.return_value = make_api_response(json_error=True)

    result = analyzer.analyze_single_stock({"종목코드": "069500", "종목명": "KODEX 200", "시장": "KOSPI"})

    assert result["2026/12(E)_ROE(%)"] == 0.0


def test_shouldReturnZeroWhenTargetYearRoeValueIsNull():
    analyzer = make_analyzer(2026)
    dataset = make_financial_dataset(["2024/12", "2025/12", "2026/12"], ["1.00", "2.00", None])

    assert analyzer.find_roe_from_financial(dataset, "000000") == 0.0


def test_shouldReturnZeroWhenTargetYearColumnIsAbsentInFinancial():
    analyzer = make_analyzer(2026)
    dataset = make_financial_dataset(["2023/12", "2024/12", "2025/12"], ["1.00", "2.00", "3.00"])

    assert analyzer.find_roe_from_financial(dataset, "000000") == 0.0
