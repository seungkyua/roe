import pytest
import pandas as pd
from bs4 import BeautifulSoup
from stock_lookup import resolve_code, fetch_price_from_api, build_result


# ── resolve_code ──────────────────────────────────────────────────────────────

def test_resolve_code_returns_code_directly_for_6digit_input():
    """6자리 숫자는 종목코드로 그대로 반환한다"""
    code = resolve_code('005930')
    assert code == '005930'


def test_resolve_code_zeropads_short_numeric_input():
    """숫자이지만 6자리 미만이면 제로패딩한다"""
    code = resolve_code('5930')
    assert code == '005930'


def test_resolve_code_searches_by_name_when_text_given(monkeypatch):
    """종목명이 주어지면 SISE 검색으로 코드를 반환한다"""
    monkeypatch.setattr('stock_lookup._search_code_by_name', lambda name: '071050')
    code = resolve_code('한국금융지주')
    assert code == '071050'


def test_resolve_code_raises_when_name_not_found(monkeypatch):
    """종목명 검색 실패 시 ValueError를 발생시킨다"""
    monkeypatch.setattr('stock_lookup._search_code_by_name', lambda name: None)
    with pytest.raises(ValueError, match='찾을 수 없습니다'):
        resolve_code('없는종목')


# ── fetch_price_from_api ──────────────────────────────────────────────────────

def test_fetch_price_from_api_returns_close_price(monkeypatch):
    """Naver polling API에서 종가(closePrice)를 int로 반환한다"""
    import stock_lookup
    mock_data = {'datas': [{'closePrice': '268,500'}]}
    monkeypatch.setattr(stock_lookup, '_call_polling_api', lambda code: mock_data)

    price = fetch_price_from_api('005930')

    assert price == 268_500


def test_fetch_price_from_api_returns_zero_on_failure(monkeypatch):
    """API 호출 실패 시 0을 반환한다"""
    import stock_lookup
    monkeypatch.setattr(stock_lookup, '_call_polling_api', lambda code: None)

    price = fetch_price_from_api('000000')

    assert price == 0


# ── build_result ──────────────────────────────────────────────────────────────

def test_build_result_contains_all_required_columns():
    """build_result()가 필수 컬럼을 모두 포함한 dict를 반환한다"""
    result = build_result(
        code='005930', name='삼성전자', market='KOSPI',
        current_roe=10.85, future_roe=29.42,
        equity=424_313_300_000_000, total_shares=5_764_191_903,
        discount_rate=10.41,
        current_price=268_500,
    )

    required = [
        '종목코드', '종목명', '시장',
        'ROE(%)', '예상ROE(%)',
        '현재가',
        '적정주가(S-RIM)', '보수적주가(S-RIM)',
        '예상적정주가(S-RIM)', '예상보수적주가(S-RIM)',
        '상승여력(%)',
    ]
    for col in required:
        assert col in result, f"'{col}' 컬럼 없음"


def test_build_result_calculates_upside_percentage():
    """상승여력(%) = (예상적정주가 - 현재가) / 현재가 * 100"""
    result = build_result(
        code='005930', name='삼성전자', market='KOSPI',
        current_roe=10.85, future_roe=29.42,
        equity=424_313_300_000_000, total_shares=5_764_191_903,
        discount_rate=10.41,
        current_price=268_500,
    )

    expected_price = result['예상적정주가(S-RIM)']
    expected_pct = (expected_price - 268_500) / 268_500 * 100
    assert result['상승여력(%)'] == pytest.approx(expected_pct, rel=1e-3)


def test_print_result_uses_box_table_format(capsys):
    """print_result()가 유니코드 박스 테이블 형태로 출력한다"""
    import stock_lookup
    result = stock_lookup.build_result(
        code='005930', name='삼성전자', market='KOSPI',
        current_roe=10.85, future_roe=29.42,
        equity=424_313_300_000_000, total_shares=5_764_191_903,
        discount_rate=10.41, current_price=268_500,
    )

    stock_lookup.print_result(result)
    captured = capsys.readouterr().out

    assert '┌' in captured and '┐' in captured   # 상단 테두리
    assert '└' in captured and '┘' in captured   # 하단 테두리
    assert '│' in captured                        # 세로 구분선
    assert '삼성전자' in captured
    assert '005930' in captured
    assert 'KOSPI' in captured
    assert '268,500' in captured
    assert '10.85' in captured
    assert '29.42' in captured


def test_build_result_sets_zero_upside_when_future_roe_is_zero():
    """예상ROE가 0이면 예상 주가와 상승여력도 0이다"""
    result = build_result(
        code='035420', name='NAVER', market='KOSPI',
        current_roe=7.2, future_roe=0.0,
        equity=100_000_000_000, total_shares=10_000_000,
        discount_rate=10.41,
        current_price=80_000,
    )

    assert result['예상적정주가(S-RIM)'] == 0
    assert result['상승여력(%)'] == 0.0


# ── FnGuide 신버전 / 네이버 자동완성 API ─────────────────────────────────────

import stock_lookup
from unittest.mock import MagicMock
from stock_fundamentals_fetcher import StockFundamentalsFetcher
from stock_roe_analyzer_final import StockROEAnalyzerFinal


def make_lookup_dataset():
    """getSnpFinancial(freq_typ=Y) dataset 모킹 (단위: 억원)"""
    cols = [
        ("2024/12", " ", "336213.63", "3916876.03", "9.03"),
        ("2025/12", " ", "442609.56", "4243132.55", "10.85"),
        ("2026/12", "E", "3125023.81", "7074608.20", "55.22"),
        ("2027/12", "E", "4455131.71", "10878945.55", "49.63"),
    ]
    header = [{"YYMM": c[0], "EP_CHK": c[1], "CD": f"VAL{i}"} for i, c in enumerate(cols, 1)]
    rows = [
        {"NAME": "  당기순이익(지배)", **{f"VAL{i}": c[2] for i, c in enumerate(cols, 1)}},
        {"NAME": "  자본총계(지배)", **{f"VAL{i}": c[3] for i, c in enumerate(cols, 1)}},
        {"NAME": "ROE", **{f"VAL{i}": c[4] for i, c in enumerate(cols, 1)}},
    ]
    return {"header": header, "data": rows}


LOOKUP_SNAPSHOT_HTML = """<html><head><title>삼성전자(005930) | Snapshot | 기업정보 | Company Guide</title></head>
<body><h1 id="giName">삼성전자</h1><span>KOSPI | 코스피 전기·전자</span>
<table><tr><th>발행주식수(보통주/ 우선주)</th><td>5,846,278,608/&nbsp; 802,371,203</td></tr></table>
<table><tr><th>주주구분</th><th>대표주주수</th><th>보통주</th><th>지분율</th></tr>
<tr><td>자사주(자사주+자사주신탁)</td><td>1</td><td>135,670,794</td><td>2.32</td></tr></table>
</body></html>"""


def test_shouldReturnSrimInputsWhenFnguideSnapshotAndFinancialApiRespond(monkeypatch):
    # API 레벨: lookup() 이 Snapshot HTML + 재무 API 에서 ROE·자본·주식수·예상ROE·종목명을 추출한다
    monkeypatch.setattr(StockFundamentalsFetcher, "get_page",
                        lambda self, code: BeautifulSoup(LOOKUP_SNAPSHOT_HTML, "html.parser"))
    monkeypatch.setattr(StockFundamentalsFetcher, "get_financial", lambda self, code: make_lookup_dataset())
    monkeypatch.setattr(StockROEAnalyzerFinal, "__init__",
                        lambda self, *a, **k: setattr(self, "target_year", 2026) or setattr(self, "target_period", "2026/12(E)"))
    monkeypatch.setattr(stock_lookup, "fetch_discount_rate", lambda: 10.78)
    monkeypatch.setattr(stock_lookup, "fetch_price_from_api", lambda code: 270_500)

    result = stock_lookup.lookup("005930")

    assert (result["종목명"], result["시장"], result["ROE(%)"], result["예상ROE(%)"], result["현재가"]) == \
        ("삼성전자", "KOSPI", 55.22, round(4455131.71 / ((7074608.20 + 10878945.55) / 2) * 100, 2), 270_500)


def make_autocomplete_session(query, items):
    """네이버 증권 자동완성 API 응답 모킹 (해당 URL 이 아니면 빈 HTML 반환)"""
    session = MagicMock()

    def fake_get(url, params=None, timeout=None):
        resp = MagicMock(text="<html></html>")
        if url == "https://ac.stock.naver.com/ac" and params == {"q": query, "target": "stock"}:
            resp.json.return_value = {"query": query, "items": items}
        else:
            resp.json.side_effect = ValueError("not json")
        return resp

    session.get.side_effect = fake_get
    return session


def test_shouldReturnCodeWhenNaverAutocompleteFindsName(monkeypatch):
    # API 레벨: 종목명 일부로 검색하면 자동완성 API 결과에서 종목코드를 반환한다
    session = make_autocomplete_session("한국금융", [
        {"code": "071050", "name": "한국금융지주", "typeCode": "KOSPI"},
        {"code": "071055", "name": "한국금융지주우", "typeCode": "KOSPI"},
    ])
    monkeypatch.setattr(stock_lookup, "_make_session", lambda *a, **k: session)

    assert stock_lookup._search_code_by_name("한국금융") == "071050"


def test_shouldPreferExactNameMatchWhenAutocompleteReturnsSeveral(monkeypatch):
    session = make_autocomplete_session("삼성전자", [
        {"code": "0162Z0", "name": "RISE 삼성전자SK하이닉스채권혼합50", "typeCode": "KOSPI"},
        {"code": "005935", "name": "삼성전자우", "typeCode": "KOSPI"},
        {"code": "005930", "name": "삼성전자", "typeCode": "KOSPI"},
    ])
    monkeypatch.setattr(stock_lookup, "_make_session", lambda *a, **k: session)

    assert stock_lookup._search_code_by_name("삼성전자") == "005930"


def test_shouldReturnNoneWhenAutocompleteHasNoMatchingStock(monkeypatch):
    session = make_autocomplete_session("없는종목", [])
    monkeypatch.setattr(stock_lookup, "_make_session", lambda *a, **k: session)

    assert stock_lookup._search_code_by_name("없는종목") is None
