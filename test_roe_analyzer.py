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
