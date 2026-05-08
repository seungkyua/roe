import pytest
import pandas as pd
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


def test_find_issued_shares_returns_common_stock_count():
    """발행주식수(보통주) 값을 정수로 반환"""
    fetcher = make_fetcher()
    soup = make_market_info_soup(issued_common=5_846_278_608, issued_preferred=802_371_203)

    issued = fetcher.find_issued_shares(soup)

    assert issued == 5_846_278_608


def test_find_treasury_shares_returns_treasury_common_stock():
    """자기주식(자사주+자사주신탁) 보통주 값을 정수로 반환"""
    fetcher = make_fetcher()
    soup = make_shareholder_soup(treasury=82_086_705)

    treasury = fetcher.find_treasury_shares(soup)

    assert treasury == 82_086_705


# ── 테스트 4: fetch() 통합 ────────────────────────────────────────────────────

def make_combined_soup(equity_map, issued_common, issued_preferred, treasury):
    """세 테이블을 하나의 HTML로 결합한 soup"""
    years = sorted(equity_map.keys())
    year_header = "".join(f"<th>{y}</th>" for y in years)
    equity_values = "".join(f"<td>{equity_map[y]:,}</td>" for y in years)
    padding = "".join("<tr><td></td></tr>" for _ in range(20))

    html = f"""<html><body>
    <!-- 시세현황 -->
    <table class="us_table_ty1">
      <tr><td>발행주식수(보통주/ 우선주)</td><td>{issued_common:,}/ {issued_preferred:,}</td></tr>
    </table>
    <!-- 주주구분 현황 -->
    <table class="us_table_ty1">
      <tr><th>주주구분</th><th>대표주주수</th><th>보통주</th><th>지분율</th></tr>
      <tr><td>자기주식 (자사주+자사주신탁)</td><td>1</td><td>{treasury:,}</td><td>1.40</td></tr>
    </table>
    <!-- Financial Highlight -->
    <table class="us_table_ty1">
      <tr><th>IFRS(연결)</th><th>Annual</th><th>Net Quarter</th></tr>
      <tr>{year_header}</tr>
      <tr><td>지배주주지분</td>{equity_values}</tr>
      {padding}
    </table>
    </body></html>"""
    return BeautifulSoup(html, 'html.parser')


def test_run_from_roe_csv_saves_fundamentals(tmp_path, monkeypatch):
    """ROE CSV에서 종목코드를 읽어 재무 데이터를 수집하고 output CSV에 저장한다"""
    roe_csv = tmp_path / "roe.csv"
    output_csv = tmp_path / "fundamentals.csv"

    pd.DataFrame([
        {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI', '2026/12(E)_ROE(%)': 10.85},
        {'종목코드': '035420', '종목명': 'NAVER',   '시장': 'KOSPI', '2026/12(E)_ROE(%)': 7.20},
    ]).to_csv(roe_csv, index=False, encoding='utf-8-sig')

    # fetch()를 mock으로 대체 (실 HTTP 차단)
    def mock_fetch(code):
        return {'종목코드': code, '자본총계(원)': 1_000_000 * 1e8, '총주식수': 5_000_000}

    fetcher = StockFundamentalsFetcher()
    monkeypatch.setattr(fetcher, 'fetch', mock_fetch)

    fetcher.run_from_roe_csv(str(roe_csv), str(output_csv))

    result = pd.read_csv(output_csv, encoding='utf-8-sig', dtype={'종목코드': str})
    assert len(result) == 2
    assert set(result['종목코드'].tolist()) == {'005930', '035420'}
    assert '자본총계(원)' in result.columns
    assert '총주식수' in result.columns


def test_fetch_returns_equity_and_total_shares(monkeypatch):
    """fetch()가 자본총계(원)과 총주식수(발행-자기주식)를 반환한다"""
    fetcher = make_fetcher(year=2026)
    mock_soup = make_combined_soup(
        equity_map={'2023/12': 3_532_338, '2024/12': 3_916_876, '2025/12': 4_243_133},
        issued_common=5_846_278_608,
        issued_preferred=802_371_203,
        treasury=82_086_705,
    )
    monkeypatch.setattr(fetcher, 'get_page', lambda code: mock_soup)

    result = fetcher.fetch('005930')

    assert result['종목코드'] == '005930'
    assert result['자본총계(원)'] == 4_243_133 * 1e8
    assert result['총주식수'] == 5_846_278_608 - 82_086_705
