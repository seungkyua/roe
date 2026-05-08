import pytest
from unittest.mock import MagicMock
from bs4 import BeautifulSoup
from stock_roe_analyzer_final import StockROEAnalyzerFinal


def make_analyzer(year=2025):
    analyzer = StockROEAnalyzerFinal.__new__(StockROEAnalyzerFinal)
    analyzer.target_year = year
    analyzer.target_period = f"{year}/12(E)"
    return analyzer


def make_soup_with_roe_table(header_cells, roe_cells):
    """재무 테이블 HTML 생성 헬퍼"""
    header_html = "".join(f"<th>{h}</th>" for h in header_cells)
    roe_cell_html = "".join(f"<td>{v}</td>" for v in roe_cells)
    # 20행 이상이어야 테이블로 인식되므로 빈 행을 채운다
    padding_rows = "".join("<tr><td></td></tr>" for _ in range(20))
    html = f"""
    <table>
      <tr>{header_html}</tr>
      <tr class="roe-row"><td>ROE(%)</td>{roe_cell_html}</tr>
      {padding_rows}
    </table>
    """
    return BeautifulSoup(html, "html.parser")


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


def make_fnguide_table_soup(year_roe_map, target_year):
    """
    FnGuide 실제 구조와 유사한 재무 테이블 HTML 생성.
    - row 0: IFRS(연결) | Annual | Net Quarter  (테이블 식별 행)
    - row 1: 빈 셀 | 연도1 | 연도2 | 연도(E) | ...  (연도 레이블 행, 데이터 행과 셀 정렬 일치)
    - data rows: 항목명 | val1 | val2 | val3 | ...
    """
    years = sorted(year_roe_map.keys())
    year_header = "<th></th>" + "".join(f"<th>{y}</th>" for y in years)
    roe_data = "<td>ROE(%)</td>" + "".join(f"<td>{year_roe_map[y]}</td>" for y in years)
    padding = "".join("<tr><td></td></tr>" for _ in range(20))
    html = f"""
    <table>
      <tr><th>IFRS(연결)</th><th>Annual</th><th>Net Quarter</th></tr>
      <tr>{year_header}</tr>
      <tr>{roe_data}</tr>
      {padding}
    </table>
    """
    return BeautifulSoup(html, "html.parser")


def test_find_roe_dynamic_year_extracts_roe_using_dynamic_column():
    analyzer = make_analyzer(year=2025)
    soup = make_fnguide_table_soup(
        {"2023/12": 8.50, "2024/12": 12.30, "2025/12(E)": 15.75},
        target_year=2025,
    )
    result = analyzer.find_roe_dynamic_year(soup, "005930")
    assert result == 15.75
