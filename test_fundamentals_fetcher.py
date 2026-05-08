import pytest
from bs4 import BeautifulSoup
from unittest.mock import patch, MagicMock
from stock_fundamentals_fetcher import StockFundamentalsFetcher


def make_fetcher(year=2026):
    f = StockFundamentalsFetcher.__new__(StockFundamentalsFetcher)
    f.current_year = year
    return f


def make_financial_highlight_soup(year_to_equity: dict):
    """
    FnGuide Financial Highlight 테이블 구조 모킹.
    - rows[0]: IFRS(연결) | Annual | Net Quarter
    - rows[1]: 연도 헤더 (레이블 셀 없이 연도만, 실제 FnGuide 구조 반영)
    - rows[2+]: 데이터 행 (셀[0]=항목명, 셀[1+]=값)
    """
    years = sorted(year_to_equity.keys())
    year_header = "".join(f"<th>{y}</th>" for y in years)
    equity_values = "".join(f"<td>{year_to_equity[y]:,}</td>" for y in years)
    padding = "".join("<tr><td></td></tr>" for _ in range(20))
    html = f"""
    <html><body>
    <table class="us_table_ty1">
      <tr><th>IFRS(연결)</th><th>Annual</th><th>Net Quarter</th></tr>
      <tr>{year_header}</tr>
      <tr><td>매출액</td>{'<td>100</td>' * len(years)}</tr>
      <tr><td>자본총계</td>{'<td>500</td>' * len(years)}</tr>
      <tr><td>지배주주지분</td>{equity_values}</tr>
      {padding}
    </table>
    </body></html>
    """
    return BeautifulSoup(html, 'html.parser')


def make_market_info_soup(issued_common: int, issued_preferred: int):
    """시세현황 테이블 모킹"""
    html = f"""
    <html><body>
    <table class="us_table_ty1">
      <tr><th>종가/ 전일대비/ 수익률</th><td>271,500</td></tr>
      <tr>
        <td>발행주식수(보통주/ 우선주)</td>
        <td>{issued_common:,}/ {issued_preferred:,}</td>
        <td>종가(NXT)</td><td>270,500</td>
      </tr>
    </table>
    </body></html>
    """
    return BeautifulSoup(html, 'html.parser')


def make_shareholder_soup(treasury: int):
    """주주구분 현황 테이블 모킹"""
    html = f"""
    <html><body>
    <table class="us_table_ty1">
      <tr><th>주주구분</th><th>대표주주수</th><th>보통주</th><th>지분율</th></tr>
      <tr><td>최대주주등</td><td>1</td><td>1,151,561,084</td><td>19.70</td></tr>
      <tr><td>자기주식 (자사주+자사주신탁)</td><td>1</td><td>{treasury:,}</td><td>1.40</td></tr>
    </table>
    </body></html>
    """
    return BeautifulSoup(html, 'html.parser')


# ── 테스트 1: find_equity ─────────────────────────────────────────────────────

def test_find_equity_returns_last_year_december_value_in_won():
    """작년 12월 지배주주지분을 억원 → 원으로 변환하여 반환"""
    fetcher = make_fetcher(year=2026)
    # current_year=2026 → last_year=2025 → '2025/12' 컬럼 찾기
    soup = make_financial_highlight_soup({
        '2023/12': 3_532_338,
        '2024/12': 3_916_876,
        '2025/12': 4_243_133,   # ← 이 값을 가져와야 함
    })

    equity = fetcher.find_equity(soup, '005930')

    assert equity == 4_243_133 * 1e8
