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

def make_financial_highlight_soup_with_colspan(year_to_equity: dict, annual_count: int = None):
    """
    FnGuide Financial Highlight 테이블 (colspan 포함).
    rows[0]: IFRS(연결) colspan=1 | Annual colspan=N | Net Quarter colspan=4
    rows[1]: 연도 헤더
    """
    years = sorted(year_to_equity.keys())
    if annual_count is None:
        annual_count = len(years)
    year_header = "".join(f"<th>{y}</th>" for y in years)
    equity_values = "".join(f"<td>{year_to_equity[y]:,}</td>" for y in years)
    padding = "".join("<tr><td></td></tr>" for _ in range(20))
    html = f"""
    <html><body>
    <table class="us_table_ty1">
      <tr>
        <th colspan="1">IFRS(연결)</th>
        <th colspan="{annual_count}">Annual</th>
        <th colspan="4">Net Quarter</th>
      </tr>
      <tr>{year_header}</tr>
      <tr><td>지배주주지분</td>{equity_values}</tr>
      {padding}
    </table>
    </body></html>
    """
    return BeautifulSoup(html, 'html.parser')


def test_find_equity_returns_last_year_december_value_in_won():
    """12월 결산 종목: 작년 12월 지배주주지분을 억원 → 원으로 변환하여 반환"""
    fetcher = make_fetcher(year=2026)
    soup = make_financial_highlight_soup_with_colspan({
        '2023/12': 3_532_338,
        '2024/12': 3_916_876,
        '2025/12': 4_243_133,   # ← Annual 마지막 실제 연도
    }, annual_count=3)

    equity = fetcher.find_equity(soup, '005930')

    assert equity == 4_243_133 * 1e8


def test_find_equity_returns_latest_annual_for_non_december_fiscal_year():
    """2월 결산 종목(950170 유형): Annual 섹션 마지막 실제 연도 컬럼 값을 반환"""
    fetcher = make_fetcher(year=2026)
    # '(P)...' 셀은 잠정실적 표시이므로 제외, '2025/02'가 최신 실제 값
    soup = make_financial_highlight_soup_with_colspan({
        '2023/02': 697,
        '2024/02': 858,
        '2025/02': 1_832,   # ← 이 값을 가져와야 함
        '(P) : Provisional잠정실적2026/02(P)': 1_897,
    }, annual_count=4)

    equity = fetcher.find_equity(soup, '950170')

    assert equity == 1_832 * 1e8


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


def test_find_treasury_shares_returns_zero_silently_when_no_treasury_row():
    """자기주식 행이 없으면 경고 없이 0을 반환"""
    fetcher = make_fetcher()
    # 자기주식 행이 없는 주주구분 테이블
    html = """<html><body>
    <table class="us_table_ty1">
      <tr><th>주주구분</th><th>대표주주수</th><th>보통주</th><th>지분율</th></tr>
      <tr><td>최대주주등</td><td>1</td><td>1,000,000</td><td>50.00</td></tr>
    </table>
    </body></html>"""
    soup = BeautifulSoup(html, 'html.parser')

    treasury = fetcher.find_treasury_shares(soup)

    assert treasury == 0


# ── 테스트 4: fetch() 통합 ────────────────────────────────────────────────────

def make_combined_soup(equity_map, issued_common, issued_preferred, treasury):
    """세 테이블을 하나의 HTML로 결합한 soup (실제 FnGuide 구조: colspan 포함)"""
    years = sorted(equity_map.keys())
    annual_count = len(years)
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
    <!-- Financial Highlight (colspan으로 Annual 경계 명시) -->
    <table class="us_table_ty1">
      <tr>
        <th colspan="1">IFRS(연결)</th>
        <th colspan="{annual_count}">Annual</th>
        <th colspan="4">Net Quarter</th>
      </tr>
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


def make_annual_extended_soup(net_income_by_year: dict, equity_by_year: dict):
    """
    IFRS(연결) Annual 확장 테이블 모킹 (Net Quarter 없음, 미래 추정치 포함).
    rows[0]: IFRS(연결) | Annual
    rows[1]: 연도 헤더 (e.g. 2023/12 | 2024/12 | 2025/12 | 2026/12(E) | ...)
    """
    years = sorted(net_income_by_year.keys())
    year_header = "".join(f"<th>{y}</th>" for y in years)
    ni_values  = "".join(f"<td>{net_income_by_year[y]:,}</td>" for y in years)
    eq_values  = "".join(f"<td>{equity_by_year[y]:,}</td>" for y in years)
    padding = "".join("<tr><td></td></tr>" for _ in range(5))
    html = f"""<html><body>
    <table>
      <tr><th colspan="1">IFRS(연결)</th><th colspan="{len(years)}">Annual</th></tr>
      <tr>{year_header}</tr>
      <tr><td>지배주주순이익</td>{ni_values}</tr>
      <tr><td>지배주주지분</td>{eq_values}</tr>
      {padding}
    </table>
    </body></html>"""
    return BeautifulSoup(html, 'html.parser')


def test_find_future_roe_calculates_from_last_two_estimates():
    """
    Annual 확장 테이블에서 마지막 추정치로 예상 ROE를 계산한다.
    ROE = 지배주주순이익 / ((전기말_지배주주지분 + 당기말_지배주주지분) / 2) * 100
    """
    fetcher = make_fetcher(year=2026)
    soup = make_annual_extended_soup(
        net_income_by_year={
            '2023/12': 144_734, '2024/12': 336_214, '2025/12': 442_610,
            '2026/12(E)': 2_771_227, '2027/12(E)': 3_463_287, '2028/12(E)': 3_413_255,
        },
        equity_by_year={
            '2023/12': 3_532_338, '2024/12': 3_916_876, '2025/12': 4_243_133,
            '2026/12(E)': 6_826_716, '2027/12(E)': 9_981_304, '2028/12(E)': 13_223_566,
        },
    )

    roe = fetcher.find_future_roe(soup, '005930')

    expected = 3_413_255 / ((9_981_304 + 13_223_566) / 2) * 100
    assert roe == pytest.approx(expected, rel=1e-3)


def make_full_page_soup(equity_map, issued_common, issued_preferred, treasury,
                        net_income_by_year, equity_by_year_extended):
    """전체 페이지 구조 모킹 (시세현황 + 주주구분 + Financial Highlight + Annual 확장)"""
    annual_count = len(equity_map)
    year_header_fh = "".join(f"<th>{y}</th>" for y in sorted(equity_map.keys()))
    equity_vals_fh = "".join(f"<td>{equity_map[y]:,}</td>" for y in sorted(equity_map.keys()))

    years_ext = sorted(net_income_by_year.keys())
    year_header_ext = "".join(f"<th>{y}</th>" for y in years_ext)
    ni_vals = "".join(f"<td>{net_income_by_year[y]:,}</td>" for y in years_ext)
    eq_vals = "".join(f"<td>{equity_by_year_extended[y]:,}</td>" for y in years_ext)
    padding = "".join("<tr><td></td></tr>" for _ in range(20))

    html = f"""<html><body>
    <table class="us_table_ty1">
      <tr><td>발행주식수(보통주/ 우선주)</td><td>{issued_common:,}/ {issued_preferred:,}</td></tr>
    </table>
    <table class="us_table_ty1">
      <tr><th>주주구분</th><th>대표주주수</th><th>보통주</th><th>지분율</th></tr>
      <tr><td>자기주식 (자사주+자사주신탁)</td><td>1</td><td>{treasury:,}</td><td>1.40</td></tr>
    </table>
    <!-- Financial Highlight (Annual+NetQ) -->
    <table class="us_table_ty1">
      <tr>
        <th colspan="1">IFRS(연결)</th>
        <th colspan="{annual_count}">Annual</th>
        <th colspan="4">Net Quarter</th>
      </tr>
      <tr>{year_header_fh}</tr>
      <tr><td>지배주주지분</td>{equity_vals_fh}</tr>
      {padding}
    </table>
    <!-- Annual 확장 (Net Quarter 없음) -->
    <table class="us_table_ty1">
      <tr>
        <th colspan="1">IFRS(연결)</th>
        <th colspan="{len(years_ext)}">Annual</th>
      </tr>
      <tr>{year_header_ext}</tr>
      <tr><td>지배주주순이익</td>{ni_vals}</tr>
      <tr><td>지배주주지분</td>{eq_vals}</tr>
      {padding}
    </table>
    </body></html>"""
    return BeautifulSoup(html, 'html.parser')


def test_fetch_returns_equity_and_total_shares(monkeypatch):
    """fetch()가 자본총계(원), 총주식수, 예상ROE(%)를 반환한다"""
    fetcher = make_fetcher(year=2026)
    mock_soup = make_full_page_soup(
        equity_map={'2023/12': 3_532_338, '2024/12': 3_916_876, '2025/12': 4_243_133},
        issued_common=5_846_278_608,
        issued_preferred=802_371_203,
        treasury=82_086_705,
        net_income_by_year={
            '2023/12': 144_734, '2024/12': 336_214, '2025/12': 442_610,
            '2026/12(E)': 2_771_227, '2027/12(E)': 3_463_287, '2028/12(E)': 3_413_255,
        },
        equity_by_year_extended={
            '2023/12': 3_532_338, '2024/12': 3_916_876, '2025/12': 4_243_133,
            '2026/12(E)': 6_826_716, '2027/12(E)': 9_981_304, '2028/12(E)': 13_223_566,
        },
    )
    monkeypatch.setattr(fetcher, 'get_page', lambda code: mock_soup)

    result = fetcher.fetch('005930')

    assert result['종목코드'] == '005930'
    assert result['자본총계(원)'] == 4_243_133 * 1e8
    assert result['총주식수'] == 5_846_278_608 - 82_086_705
    expected_roe = 3_413_255 / ((9_981_304 + 13_223_566) / 2) * 100
    assert result['예상ROE(%)'] == pytest.approx(expected_roe, rel=1e-3)
