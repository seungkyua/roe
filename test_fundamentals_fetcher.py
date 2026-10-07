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


# ── FnGuide 신버전 (Snapshot HTML + getSnpFinancial API) ─────────────────────

def make_snapshot_html(issued_common, issued_preferred, treasury):
    """신버전 Snapshot 페이지 구조 모킹 (시세현황 + 주주현황 상위 6 + 주주구분 현황)"""
    return f"""<html><body>
    <h1 id="giName">삼성전자</h1>
    <table><caption>시세현황</caption>
      <tr><th><div>발행주식수<span>(보통주/ 우선주)</span></div></th>
          <td>{issued_common:,}/&nbsp; {issued_preferred:,}</td></tr>
    </table>
    <table><caption>주주현황</caption>
      <tr><th>항목</th><th>보통주</th><th>지분율</th><th>최종변동일</th></tr>
      <tr><td>자사주</td><td>{treasury:,}</td><td>2.32</td><td>2026/10/02</td></tr>
    </table>
    <table><caption>주주현황</caption>
      <tr><th>주주구분</th><th>대표주주수</th><th>보통주</th><th>지분율</th><th>최종변동일</th></tr>
      <tr><td>자사주(자사주+자사주신탁)</td><td>1</td><td>{treasury:,}</td><td>2.32</td><td>2026/10/02</td></tr>
    </table>
    </body></html>"""


def make_annual_dataset(columns):
    """getSnpFinancial(freq_typ=Y) dataset 모킹.
    columns: [(YYMM, EP_CHK, 당기순이익(지배), 자본총계(지배)), ...] (값 단위: 억원, 문자열 또는 None)"""
    header = [{"YYMM": yymm, "EP_CHK": ep, "CD": f"VAL{i}"} for i, (yymm, ep, _, _) in enumerate(columns, 1)]
    net_income = {"NAME": "  당기순이익(지배)", **{f"VAL{i}": c[2] for i, c in enumerate(columns, 1)}}
    equity = {"NAME": "  자본총계(지배)", **{f"VAL{i}": c[3] for i, c in enumerate(columns, 1)}}
    return {"header": header, "data": [{"NAME": "매출액"}, net_income, equity]}


SAMSUNG_ANNUAL = make_annual_dataset([
    ("2023/12", " ", "144734.01", "3532337.75"),
    ("2024/12", " ", "336213.63", "3916876.03"),
    ("2025/12", " ", "442609.56", "4243132.55"),
    ("2026/12", "E", "3125023.81", "7074608.20"),
    ("2027/12", "E", "4455131.71", "10878945.55"),
    ("2028/12", "E", "4866517.82", "14997323.12"),
])


def test_shouldReturnFundamentalsWhenFnguideSnapshotAndFinancialApiRespond():
    # API 레벨: Snapshot HTML(발행주식수/자사주) + 재무 API(지배주주지분/예상ROE)를 조합한다
    fetcher = make_fetcher(year=2026)
    snapshot = MagicMock(text=make_snapshot_html(5_846_278_608, 802_371_203, 135_670_794))
    financial = MagicMock()
    financial.json.return_value = {"dataset": SAMSUNG_ANNUAL}

    def fake_get(url, params=None, timeout=None):
        assert params["cmp_cd"] == "005930"
        return {"Snapshot": snapshot, "getSnpFinancial": financial}[url.rsplit("/", 1)[-1]]

    fetcher.session = MagicMock()
    fetcher.session.get.side_effect = fake_get

    result = fetcher.fetch("005930")

    assert result == {
        "종목코드": "005930",
        "자본총계(원)": pytest.approx(4243132.55 * 1e8),
        "총주식수": 5_846_278_608 - 135_670_794,
        "예상ROE(%)": round(4866517.82 / ((10878945.55 + 14997323.12) / 2) * 100, 2),
    }


def test_shouldReturnTreasurySharesWhenLabelIsJasajuWithTrust():
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(make_snapshot_html(1_000, 0, 77), "html.parser")

    assert make_fetcher().find_treasury_shares(soup) == 77


def test_shouldReturnLatestActualEquityWhenFiscalYearIsNotDecember():
    dataset = make_annual_dataset([
        ("2025/02", " ", "772.31", "1829.99"),
        ("2026/02", " ", "48.46", "1714.35"),
        ("2027/02", "E", None, None),
    ])

    assert make_fetcher().find_equity_from_financial(dataset, "950170") == pytest.approx(1714.35 * 1e8)


def test_shouldReturnZeroFutureRoeWhenLastEstimateIsNull():
    dataset = make_annual_dataset([
        ("2025/02", " ", "772.31", "1829.99"),
        ("2026/02", " ", "48.46", "1714.35"),
        ("2027/02", "E", None, None),
    ])

    assert make_fetcher().find_future_roe_from_financial(dataset, "950170") == 0.0
