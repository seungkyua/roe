import pytest
import pandas as pd
from bs4 import BeautifulSoup
from s_rim import SRIMCalculator
from s_rim_pipeline import merge_inputs, SRIMPipeline, fetch_discount_rate, sort_results


# ── SRIMCalculator ────────────────────────────────────────────────────────────

def make_calc(discount_rate=9.24):
    return SRIMCalculator(discount_rate=discount_rate)


def test_proper_price_returns_srim_valuation():
    """기본 S-RIM: V = equity + equity*(ROE-r)/r, price = V / total_shares"""
    calc = make_calc(discount_rate=9.24)
    equity = 126_800_000_000
    roe = 31.95
    total_shares = 89_968_897 - 3_793

    price = calc.proper_price(equity, roe, total_shares)

    # cal_proper_values 직접 계산값과 일치해야 함
    from s_rim import cal_proper_values
    _, expected = cal_proper_values(9.24, equity, roe, total_shares)
    assert price == expected


def test_conservative_price_returns_supernormal_valuation():
    """초과이익 10% 감소 모델로 보수적 주가 반환"""
    calc = make_calc(discount_rate=9.24)
    equity = 126_800_000_000
    roe = 31.95
    total_shares = 89_968_897 - 3_793

    price = calc.conservative_price(equity, roe, total_shares)

    from s_rim import cal_supernormal_values
    expected = cal_supernormal_values(9.24, equity, roe, total_shares)
    assert price == expected


def test_calc_row_adds_both_prices_to_dict():
    """calc_row()가 입력 dict에 적정주가와 보수적주가를 추가한 dict를 반환"""
    calc = make_calc(discount_rate=9.24)
    row = {
        '종목코드': '071280',
        '종목명': '원텍',
        '시장': 'KOSDAQ',
        'ROE(%)': 31.95,
        '자본총계(원)': 126_800_000_000,
        '총주식수': 89_968_897 - 3_793,
    }

    result = calc.calc_row(row)

    assert '적정주가(S-RIM)' in result
    assert '보수적주가(S-RIM)' in result
    assert result['적정주가(S-RIM)'] == calc.proper_price(row['자본총계(원)'], row['ROE(%)'], row['총주식수'])
    assert result['보수적주가(S-RIM)'] == calc.conservative_price(row['자본총계(원)'], row['ROE(%)'], row['총주식수'])
    assert result['종목코드'] == '071280'


def test_calc_row_adds_future_prices_when_expected_roe_present():
    """예상ROE(%)가 0보다 크면 예상적정주가(S-RIM)와 예상보수적주가(S-RIM)를 추가한다"""
    calc = make_calc(discount_rate=9.24)
    row = {
        '종목코드': '005930',
        '종목명': '삼성전자',
        '시장': 'KOSPI',
        'ROE(%)': 10.85,
        '자본총계(원)': 424_313_300_000_000,
        '총주식수': 5_764_191_903,
        '예상ROE(%)': 29.42,
    }

    result = calc.calc_row(row)

    assert '예상적정주가(S-RIM)' in result
    assert '예상보수적주가(S-RIM)' in result
    assert result['예상적정주가(S-RIM)'] == calc.proper_price(
        row['자본총계(원)'], row['예상ROE(%)'], row['총주식수']
    )
    assert result['예상보수적주가(S-RIM)'] == calc.conservative_price(
        row['자본총계(원)'], row['예상ROE(%)'], row['총주식수']
    )


def test_calc_row_sets_future_prices_to_zero_when_expected_roe_is_zero():
    """예상ROE(%)가 0이면 예상적정주가(S-RIM)와 예상보수적주가(S-RIM)는 0을 반환한다"""
    calc = make_calc(discount_rate=9.24)
    row = {
        '종목코드': '000000',
        '종목명': '테스트',
        '시장': 'KOSPI',
        'ROE(%)': 15.0,
        '자본총계(원)': 100_000_000_000,
        '총주식수': 10_000_000,
        '예상ROE(%)': 0.0,
    }

    result = calc.calc_row(row)

    assert result['예상적정주가(S-RIM)'] == 0
    assert result['예상보수적주가(S-RIM)'] == 0


# ── merge_inputs ──────────────────────────────────────────────────────────────

def make_roe_df(rows):
    return pd.DataFrame([
        {'종목코드': code, '종목명': name, '2026/12(E)_ROE(%)': roe}
        for code, name, roe in rows
    ])

def make_fundamentals_df(rows):
    return pd.DataFrame([
        {'종목코드': code, '자본총계(원)': equity, '총주식수': shares}
        for code, equity, shares in rows
    ])


def test_merge_inputs_joins_on_stock_code():
    """두 DataFrame이 종목코드 기준으로 병합된다"""
    roe_df = make_roe_df([('005930', '삼성전자', 12.5), ('035420', 'NAVER', 7.2)])
    fundamentals_df = make_fundamentals_df([('005930', 300_000_000_000, 5_000_000)])

    merged = merge_inputs(roe_df, fundamentals_df)

    assert len(merged) == 1
    assert merged.iloc[0]['종목코드'] == '005930'
    assert '2026/12(E)_ROE(%)' in merged.columns
    assert '자본총계(원)' in merged.columns


def test_merge_inputs_excludes_unmatched_stocks():
    """한쪽에만 있는 종목은 결과에서 제외된다"""
    roe_df = make_roe_df([('005930', '삼성전자', 12.5), ('000660', 'SK하이닉스', 20.0)])
    fundamentals_df = make_fundamentals_df([('000660', 200_000_000_000, 7_000_000)])

    merged = merge_inputs(roe_df, fundamentals_df)

    codes = merged['종목코드'].tolist()
    assert '000660' in codes
    assert '005930' not in codes


# ── SRIMPipeline.run() ────────────────────────────────────────────────────────

def test_load_normalizes_roe_column_name(tmp_path, monkeypatch):
    """ROE CSV의 YYYY/12(E)_ROE(%) 컬럼이 ROE(%)로 정규화된다"""
    monkeypatch.setattr('s_rim_pipeline.fetch_discount_rate', lambda: 9.24)
    roe_csv = tmp_path / "roe.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"

    pd.DataFrame([
        {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI', '2026/12(E)_ROE(%)': 10.85},
    ]).to_csv(roe_csv, index=False, encoding='utf-8-sig')

    pd.DataFrame([
        {'종목코드': '005930', '자본총계(원)': 4_243_133 * 1e8, '총주식수': 5_764_191_903},
    ]).to_csv(fundamentals_csv, index=False, encoding='utf-8-sig')

    pipeline = SRIMPipeline(str(roe_csv), str(fundamentals_csv))
    merged = pipeline.load()

    assert 'ROE(%)' in merged.columns
    assert '2026/12(E)_ROE(%)' not in merged.columns
    assert merged.iloc[0]['ROE(%)'] == pytest.approx(10.85)


def test_pipeline_run_applies_srim_to_merged_data(tmp_path, monkeypatch):
    """run()이 병합 데이터 전체에 S-RIM 계산을 적용한 DataFrame을 반환한다"""
    monkeypatch.setattr('s_rim_pipeline.fetch_discount_rate', lambda: 9.24)
    roe_csv = tmp_path / "roe.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"

    pd.DataFrame([
        {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI', 'ROE(%)': 12.5},
        {'종목코드': '035420', '종목명': 'NAVER', '시장': 'KOSPI', 'ROE(%)': 7.2},
    ]).to_csv(roe_csv, index=False, encoding='utf-8-sig')

    pd.DataFrame([
        {'종목코드': '005930', '자본총계(원)': 300_000_000_000, '총주식수': 5_000_000},
    ]).to_csv(fundamentals_csv, index=False, encoding='utf-8-sig')

    pipeline = SRIMPipeline(str(roe_csv), str(fundamentals_csv))
    result = pipeline.run()

    assert len(result) == 1
    assert result.iloc[0]['종목코드'] == '005930'
    assert '적정주가(S-RIM)' in result.columns
    assert '보수적주가(S-RIM)' in result.columns
    assert result.iloc[0]['적정주가(S-RIM)'] > 0


# ── fetch_discount_rate ───────────────────────────────────────────────────────

def make_kis_rating_soup(bbb_minus_5y: float) -> BeautifulSoup:
    """KIS Rating 등급별 금리스프레드 테이블 모킹 (테이블[0] 구조)"""
    html = f"""<html><body>
    <table>
      <tr><th>구분</th><th>3월</th><th>6월</th><th>9월</th><th>1년</th>
          <th>1년6월</th><th>2년</th><th>3년</th><th>5년</th></tr>
      <tr><td>국고채</td><td>2.62</td><td>2.70</td><td>2.80</td><td>3.01</td>
          <td>3.25</td><td>3.45</td><td>3.56</td><td>3.74</td></tr>
      <tr><td>AAA</td><td>2.88</td><td>2.96</td><td>3.11</td><td>3.30</td>
          <td>3.62</td><td>3.89</td><td>4.03</td><td>4.09</td></tr>
      <tr><td>AA+</td><td>2.90</td><td>3.00</td><td>3.15</td><td>3.35</td>
          <td>3.68</td><td>3.97</td><td>4.10</td><td>4.15</td></tr>
      <tr><td>AA</td><td>2.93</td><td>3.03</td><td>3.20</td><td>3.40</td>
          <td>3.75</td><td>4.05</td><td>4.18</td><td>4.23</td></tr>
      <tr><td>AA-</td><td>2.97</td><td>3.09</td><td>3.27</td><td>3.47</td>
          <td>3.84</td><td>4.15</td><td>4.30</td><td>4.35</td></tr>
      <tr><td>A+</td><td>3.07</td><td>3.24</td><td>3.45</td><td>3.66</td>
          <td>4.08</td><td>4.43</td><td>4.62</td><td>4.71</td></tr>
      <tr><td>A</td><td>3.19</td><td>3.39</td><td>3.63</td><td>3.86</td>
          <td>4.31</td><td>4.70</td><td>4.93</td><td>5.05</td></tr>
      <tr><td>A-</td><td>3.34</td><td>3.59</td><td>3.87</td><td>4.13</td>
          <td>4.61</td><td>5.05</td><td>5.35</td><td>5.52</td></tr>
      <tr><td>BBB+</td><td>3.74</td><td>4.21</td><td>4.76</td><td>5.10</td>
          <td>5.98</td><td>6.90</td><td>7.60</td><td>7.95</td></tr>
      <tr><td>BBB</td><td>4.12</td><td>4.72</td><td>5.34</td><td>5.77</td>
          <td>6.79</td><td>7.84</td><td>8.64</td><td>8.99</td></tr>
      <tr><td>BBB-</td><td>4.79</td><td>5.51</td><td>6.28</td><td>6.77</td>
          <td>7.91</td><td>9.01</td><td>10.02</td><td>{bbb_minus_5y}</td></tr>
    </table>
    </body></html>"""
    return BeautifulSoup(html, 'html.parser')


def test_fetch_discount_rate_returns_bbb_minus_5y_rate(monkeypatch):
    """KIS Rating 페이지에서 BBB- 5년 금리를 float로 반환한다"""
    mock_soup = make_kis_rating_soup(bbb_minus_5y=10.41)

    def mock_get_kis_page():
        return mock_soup

    monkeypatch.setattr('s_rim_pipeline._get_kis_rating_page', mock_get_kis_page)

    rate = fetch_discount_rate()

    assert rate == pytest.approx(10.41)


def test_pipeline_uses_auto_fetched_discount_rate(tmp_path, monkeypatch):
    """discount_rate 없이 생성한 SRIMPipeline이 자동 조회한 금리를 사용한다"""
    roe_csv = tmp_path / "roe.csv"
    fundamentals_csv = tmp_path / "fundamentals.csv"

    pd.DataFrame([
        {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI', 'ROE(%)': 12.5},
    ]).to_csv(roe_csv, index=False, encoding='utf-8-sig')

    pd.DataFrame([
        {'종목코드': '005930', '자본총계(원)': 300_000_000_000, '총주식수': 5_000_000},
    ]).to_csv(fundamentals_csv, index=False, encoding='utf-8-sig')

    monkeypatch.setattr('s_rim_pipeline.fetch_discount_rate', lambda: 10.41)

    pipeline = SRIMPipeline(str(roe_csv), str(fundamentals_csv))
    result = pipeline.run()

    assert result.iloc[0]['할인율(%)'] == pytest.approx(10.41)
    assert result.iloc[0]['적정주가(S-RIM)'] > 0


# ── sort_results ──────────────────────────────────────────────────────────────

def make_srim_df_for_sort():
    return pd.DataFrame([
        {'종목코드': 'A', '종목명': 'α', '시장': 'KOSPI',
         '적정주가(S-RIM)': 100_000, '예상적정주가(S-RIM)': 150_000, '현재가': 80_000},
        {'종목코드': 'B', '종목명': 'β', '시장': 'KOSPI',
         '적정주가(S-RIM)': 50_000,  '예상적정주가(S-RIM)': 200_000, '현재가': 90_000},
        {'종목코드': 'C', '종목명': 'γ', '시장': 'KOSPI',
         '적정주가(S-RIM)': 200_000, '예상적정주가(S-RIM)': 180_000, '현재가': 70_000},
    ])


def test_sort_results_by_proper_vs_current():
    """'proper': (적정주가 - 현재가) / 현재가 * 100 내림차순"""
    df = make_srim_df_for_sort()
    # A: (100k-80k)/80k = 25%
    # B: (50k-90k)/90k = -44.4%
    # C: (200k-70k)/70k = 185.7%  ← 1위

    result = sort_results(df, mode='proper')

    assert result.iloc[0]['종목코드'] == 'C'
    assert '정렬기준(%)' in result.columns


def test_sort_results_by_expected_vs_current():
    """'expected': (예상적정주가 - 현재가) / 현재가 * 100 내림차순"""
    df = make_srim_df_for_sort()
    # A: (150k-80k)/80k = 87.5%
    # B: (200k-90k)/90k = 122.2%  ← 1위
    # C: (180k-70k)/70k = 157.1%  ← 실제 1위

    result = sort_results(df, mode='expected')

    assert result.iloc[0]['종목코드'] == 'C'
    assert '정렬기준(%)' in result.columns


def test_sort_results_by_growth():
    """'growth': (예상적정주가 - 적정주가) / 적정주가 * 100 내림차순"""
    df = make_srim_df_for_sort()
    # A: (150k-100k)/100k = 50%
    # B: (200k-50k)/50k  = 300%  ← 1위
    # C: (180k-200k)/200k = -10%

    result = sort_results(df, mode='growth')

    assert result.iloc[0]['종목코드'] == 'B'
    assert '정렬기준(%)' in result.columns


def test_sort_results_raises_on_invalid_mode():
    df = make_srim_df_for_sort()
    with pytest.raises(ValueError, match='mode'):
        sort_results(df, mode='invalid')
