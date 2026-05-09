#!/usr/bin/env python3
"""
종목 코드 또는 종목명으로 S-RIM 적정 주가 실시간 계산 (CSV 파일 없음)

HTTP 요청 흐름 (총 3~4회):
  1. FnGuide 페이지  → ROE, equity, total_shares, future_roe
  2. KIS Rating     → discount_rate (BBB- 5년)
  3. Naver polling  → 현재가
  4. Naver SISE     → 종목명 입력 시 코드 변환 (병렬)

사용 예:
  python stock_lookup.py 005930
  python stock_lookup.py 삼성전자
  python stock_lookup.py 한국금융지주
"""

import argparse
import logging
import re
import sys
import time
import unicodedata
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed

from stock_roe_analyzer_final import StockROEAnalyzerFinal
from stock_fundamentals_fetcher import StockFundamentalsFetcher
from s_rim import SRIMCalculator
from s_rim_pipeline import fetch_discount_rate

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

NAVER_SISE_KOSPI  = "https://finance.naver.com/sise/sise_market_sum.nhn"
NAVER_SISE_KOSDAQ = "https://finance.naver.com/sise/sise_market_sum.nhn?sosok=1"
POLLING_API_URL   = "https://polling.finance.naver.com/api/realtime/domestic/stock/{code}"

DISPLAY_COLUMNS = [
    '종목코드', '종목명', '시장',
    'ROE(%)', '예상ROE(%)',
    '현재가',
    '적정주가(S-RIM)', '보수적주가(S-RIM)',
    '예상적정주가(S-RIM)', '예상보수적주가(S-RIM)',
    '상승여력(%)',
]


# ── HTTP 헬퍼 ─────────────────────────────────────────────────────────────────

def _make_session(pool_maxsize: int = 10) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'ko-KR,ko;q=0.9',
    })
    # 병렬 요청 시 커넥션 풀 부족 경고 방지
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=pool_maxsize)
    s.mount('https://', adapter)
    s.mount('http://', adapter)
    return s


def _call_polling_api(stock_code: str) -> dict | None:
    """Naver Finance polling API 호출 → 원시 JSON 반환"""
    try:
        session = _make_session()
        resp = session.get(POLLING_API_URL.format(code=stock_code), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.warning(f"{stock_code} 현재가 API 호출 실패: {e}")
        return None


def _fetch_sise_page(url: str, session: requests.Session) -> list[dict]:
    """Naver Finance SISE 1개 페이지에서 종목 목록 반환"""
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        resp.encoding = 'euc-kr'
        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table', {'class': 'type_2'})
        if not table:
            return []
        stocks = []
        for row in table.find_all('tr'):
            link = row.find('a', href=re.compile(r'code=\d{6}'))
            if link:
                m = re.search(r'code=(\d{6})', link['href'])
                if m:
                    market = 'KOSDAQ' if 'sosok=1' in url else 'KOSPI'
                    stocks.append({
                        '종목코드': m.group(1),
                        '종목명': link.get_text(strip=True),
                        '시장': market,
                    })
        return stocks
    except Exception as e:
        logger.debug(f"SISE 페이지 오류 ({url}): {e}")
        return []


def _get_total_sise_pages(soup: BeautifulSoup) -> int:
    """페이지 네비게이션에서 전체 페이지 수 추출"""
    try:
        for link in soup.find_all('a', href=re.compile(r'page=\d+')):
            if link.get_text(strip=True) == '맨뒤':
                m = re.search(r'page=(\d+)', link['href'])
                if m:
                    return int(m.group(1))
        nums = [int(m.group(1)) for a in soup.find_all('a', href=re.compile(r'page=\d+'))
                if (m := re.search(r'page=(\d+)', a['href']))]
        return max(nums) if nums else 30
    except Exception:
        return 30


# ── 공개 API ──────────────────────────────────────────────────────────────────

def _search_code_by_name(name: str) -> str | None:
    """
    Naver Finance SISE 페이지를 병렬로 검색해 종목명과 일치하는 종목코드 반환.
    없으면 None.

    최적화:
    - 1페이지 fetch 에서 soup을 재사용해 전체 페이지 수도 한 번에 파악 (이중 요청 제거)
    - 공유 세션의 커넥션 풀을 병렬 워커 수에 맞게 확대
    """
    WORKERS = 10
    name_lower = name.strip().lower()

    def _search_market(base_url: str) -> str | None:
        # 시장별 독립 세션 — 세션 공유 시 pool_maxsize 경쟁 방지
        sess = _make_session(pool_maxsize=WORKERS + 5)

        # 1페이지 fetch — soup에서 종목 목록 + 전체 페이지 수를 동시에 추출
        try:
            resp = sess.get(base_url, timeout=15)
            resp.raise_for_status()
            resp.encoding = 'euc-kr'
            soup = BeautifulSoup(resp.text, 'html.parser')
        except Exception as e:
            logger.debug(f"SISE 1페이지 오류 ({base_url}): {e}")
            return None

        # 1페이지 종목 검색
        table = soup.find('table', {'class': 'type_2'})
        if table:
            for row in table.find_all('tr'):
                link = row.find('a', href=re.compile(r'code=\d{6}'))
                if link and name_lower in link.get_text(strip=True).lower():
                    m = re.search(r'code=(\d{6})', link['href'])
                    if m:
                        return m.group(1)

        # 전체 페이지 수 (1페이지 soup 재사용)
        total = _get_total_sise_pages(soup)

        # 2페이지 이후 병렬 검색
        sep = '&' if 'sosok=1' in base_url else '?'
        urls = [f"{base_url}{sep}page={p}" for p in range(2, total + 1)]

        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futures = {ex.submit(_fetch_sise_page, u, sess): u for u in urls}
            for future in as_completed(futures):
                for s in (future.result() or []):
                    if name_lower in s['종목명'].lower():
                        return s['종목코드']
        return None

    # KOSPI, KOSDAQ 병렬 검색 (각자 독립 세션 사용)
    with ThreadPoolExecutor(max_workers=2) as ex:
        kospi_f  = ex.submit(_search_market, NAVER_SISE_KOSPI)
        kosdaq_f = ex.submit(_search_market, NAVER_SISE_KOSDAQ)
        for future in as_completed([kospi_f, kosdaq_f]):
            result = future.result()
            if result:
                return result
    return None


def resolve_code(query: str) -> str:
    """
    쿼리가 숫자면 종목코드로, 문자면 종목명 검색으로 코드를 반환.
    """
    stripped = query.strip()
    if stripped.isdigit():
        return stripped.zfill(6)

    code = _search_code_by_name(stripped)
    if not code:
        raise ValueError(f"'{stripped}' 에 해당하는 종목을 찾을 수 없습니다.")
    return code


def fetch_price_from_api(stock_code: str) -> int:
    """Naver Finance polling API에서 현재가(종가) 반환 (실패 시 0)"""
    data = _call_polling_api(stock_code)
    if data is None:
        return 0
    try:
        price_str = data['datas'][0]['closePrice'].replace(',', '')
        return int(price_str)
    except (KeyError, IndexError, ValueError) as e:
        logger.warning(f"{stock_code} 현재가 파싱 실패: {e}")
        return 0


def build_result(
    code: str, name: str, market: str,
    current_roe: float, future_roe: float,
    equity: float, total_shares: int,
    discount_rate: float, current_price: int,
) -> dict:
    """S-RIM 계산 결과 dict 반환"""
    calc = SRIMCalculator(discount_rate)

    proper  = calc.proper_price(equity, current_roe, total_shares) if current_roe > 0 else 0
    conserv = calc.conservative_price(equity, current_roe, total_shares) if current_roe > 0 else 0

    if future_roe > 0:
        exp_proper  = calc.proper_price(equity, future_roe, total_shares)
        exp_conserv = calc.conservative_price(equity, future_roe, total_shares)
        upside_pct  = round((exp_proper - current_price) / current_price * 100, 2) if current_price > 0 else 0.0
    else:
        exp_proper = exp_conserv = 0
        upside_pct = 0.0

    return {
        '종목코드':             code,
        '종목명':              name,
        '시장':               market,
        'ROE(%)':            round(current_roe, 2),
        '예상ROE(%)':         round(future_roe, 2),
        '현재가':              current_price,
        '적정주가(S-RIM)':     proper,
        '보수적주가(S-RIM)':    conserv,
        '예상적정주가(S-RIM)':  exp_proper,
        '예상보수적주가(S-RIM)': exp_conserv,
        '상승여력(%)':         upside_pct,
    }


def _dw(s: str) -> int:
    """CJK 문자를 2칸으로 계산한 디스플레이 폭"""
    return sum(2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1 for c in s)


def _ljust(s: str, width: int) -> str:
    """디스플레이 폭 기준 왼쪽 정렬"""
    return s + ' ' * max(0, width - _dw(s))


def _rjust(s: str, width: int) -> str:
    """디스플레이 폭 기준 오른쪽 정렬"""
    return ' ' * max(0, width - _dw(s)) + s


def print_result(result: dict) -> None:
    """유니코드 박스 테이블로 결과 출력"""
    LW = 26   # 레이블 열 디스플레이 폭
    VW = 20   # 값 열 디스플레이 폭

    def hline(l, m, r):
        return f"{l}{'─'*(LW+2)}{m}{'─'*(VW+2)}{r}"

    def row(label: str, value: str) -> str:
        return f"│ {_ljust(label, LW)} │ {_rjust(value, VW)} │"

    def fmt_price(n) -> str:
        return f"{int(n):,} 원" if n and int(n) != 0 else "         -  원"

    def fmt_pct(v: float, signed: bool = False) -> str:
        return f"{v:+.2f} %" if signed else f"{v:.2f} %"

    # ── 헤더 ──────────────────────────────────────────────────
    name   = result.get('종목명', '')
    code   = result.get('종목코드', '')
    market = result.get('시장', '')

    inner_w   = LW + VW + 5          # │ 제외 내부 폭
    title     = f"  {name} ({code})"
    mkt       = f"{market}  "
    gap       = inner_w - _dw(title) - _dw(mkt)
    hdr_inner = title + ' ' * max(1, gap) + mkt

    print()
    print(f"┌{'─'*(inner_w)}┐")
    print(f"│{hdr_inner}│")
    print(hline('├', '┬', '┤'))

    # ── 현재가 ───────────────────────────────────────────────
    print(row("현재가", fmt_price(result['현재가'])))
    print(hline('├', '┼', '┤'))

    # ── ROE ──────────────────────────────────────────────────
    print(row("ROE (%)",      fmt_pct(result['ROE(%)'])))
    print(row("예상 ROE (%)", fmt_pct(result['예상ROE(%)'])))
    print(hline('├', '┼', '┤'))

    # ── 적정 주가 ─────────────────────────────────────────────
    print(row("적정주가 (S-RIM)",  fmt_price(result['적정주가(S-RIM)'])))
    print(row("보수적주가 (S-RIM)", fmt_price(result['보수적주가(S-RIM)'])))
    print(hline('├', '┼', '┤'))

    # ── 예상 적정 주가 ────────────────────────────────────────
    print(row("예상적정주가 (S-RIM)",  fmt_price(result['예상적정주가(S-RIM)'])))
    print(row("예상보수적주가 (S-RIM)", fmt_price(result['예상보수적주가(S-RIM)'])))
    print(hline('├', '┼', '┤'))

    # ── 상승여력 ──────────────────────────────────────────────
    print(row("상승여력 (%)", fmt_pct(result['상승여력(%)'], signed=True)))
    print(hline('└', '┴', '┘'))
    print()


def lookup(query: str) -> dict:
    """종목코드 또는 종목명으로 실시간 S-RIM 계산 수행"""
    # 1. 코드 해석
    logger.info(f"종목 검색: '{query}'")
    code = resolve_code(query)
    logger.info(f"종목코드: {code}")

    # 2. FnGuide 페이지 1회 fetch → ROE + 재무데이터 동시 추출
    logger.info("FnGuide 재무 데이터 수집 중...")
    roe_analyzer   = StockROEAnalyzerFinal()
    fund_fetcher   = StockFundamentalsFetcher()

    soup = fund_fetcher.get_page(code)
    if soup is None:
        raise RuntimeError(f"FnGuide 페이지를 가져올 수 없습니다: {code}")

    # ROE (당해연도 예상), equity, total_shares, future_roe — 동일 페이지에서 추출
    current_roe  = roe_analyzer.find_roe_dynamic_year(soup, code) or 0.0
    equity       = fund_fetcher.find_equity(soup, code)
    issued       = fund_fetcher.find_issued_shares(soup)
    treasury     = fund_fetcher.find_treasury_shares(soup)
    total_shares = issued - treasury
    future_roe   = fund_fetcher.find_future_roe(soup, code)

    # 종목명·시장 추출 (FnGuide 타이틀: "삼성전자(A005930) | ...")
    name, market = _extract_name_market(soup, code)

    # 3. 할인율 (KIS Rating BBB- 5년)
    logger.info("KIS Rating 할인율 조회 중...")
    discount_rate = fetch_discount_rate()

    # 4. 현재가 (Naver polling API)
    logger.info("현재가 조회 중...")
    current_price = fetch_price_from_api(code)

    return build_result(
        code=code, name=name, market=market,
        current_roe=current_roe, future_roe=future_roe,
        equity=equity, total_shares=total_shares,
        discount_rate=discount_rate,
        current_price=current_price,
    )


def _extract_name_market(soup, code: str) -> tuple[str, str]:
    """FnGuide 페이지에서 종목명과 시장 추출"""
    name = market = ''
    # title: "삼성전자(A005930) | Snapshot | ..."
    title = soup.find('title')
    if title:
        m = re.match(r'^(.+?)\(A\d{6}\)', title.get_text(strip=True))
        if m:
            name = m.group(1).strip()

    # #giName
    if not name:
        el = soup.select_one('#giName')
        if el:
            name = el.get_text(strip=True)

    # 시장 구분
    body_text = soup.get_text()
    if 'KOSDAQ' in body_text:
        market = 'KOSDAQ'
    elif 'KOSPI' in body_text or 'KS' in body_text:
        market = 'KOSPI'

    return name or code, market


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='S-RIM 적정 주가 실시간 조회 (CSV 불필요)')
    parser.add_argument('query', help='종목코드(6자리) 또는 종목명')
    args = parser.parse_args()

    try:
        result = lookup(args.query)
        print_result(result)
    except ValueError as e:
        print(f"\n오류: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"\n오류: {e}")
        sys.exit(1)
