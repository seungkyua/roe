import importlib
from unittest.mock import MagicMock, patch

# 파일명이 숫자로 시작하므로 import 문 대신 importlib 로 불러온다
stock_list_manual = importlib.import_module('01_stock_list_manual')
StockListManager = stock_list_manual.StockListManager


def make_response(total_count, items):
    """네이버 증권 marketValue API 응답 모킹"""
    resp = MagicMock()
    resp.json.return_value = {'totalCount': total_count, 'stocks': items}
    resp.raise_for_status.return_value = None
    return resp


def item(code, name):
    return {'itemCode': code, 'stockName': name}


@patch.object(stock_list_manual.time, 'sleep')
def test_shouldReturnKospiAndKosdaqStocksWhenNaverApiResponds(_sleep):
    # API 레벨: 시장별 API 응답을 합쳐 종목코드/종목명/시장 DataFrame을 만든다
    manager = StockListManager()
    responses = {
        'KOSPI': make_response(1, [item('005930', '삼성전자')]),
        'KOSDAQ': make_response(1, [item('196170', '알테오젠')]),
    }
    manager.session.get = MagicMock(side_effect=lambda url, **kwargs: responses[url.rsplit('/', 1)[-1]])

    df = manager.scrape_stocks_from_naver_finance()

    assert df.to_dict('records') == [
        {'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSPI'},
        {'종목코드': '196170', '종목명': '알테오젠', '시장': 'KOSDAQ'},
    ]


@patch.object(stock_list_manual.time, 'sleep')
def test_shouldFetchAllPagesWhenTotalCountExceedsPageSize(_sleep):
    manager = StockListManager()
    pages = {
        1: make_response(3, [item('005930', '삼성전자'), item('000660', 'SK하이닉스')]),
        2: make_response(3, [item('373220', 'LG에너지솔루션')]),
    }
    manager.session.get = MagicMock(side_effect=lambda url, params, timeout: pages[params['page']])

    stocks = manager.scrape_market_stocks('KOSPI', page_size=2)

    assert [s['종목코드'] for s in stocks] == ['005930', '000660', '373220']


@patch.object(stock_list_manual.time, 'sleep')
def test_shouldSkipInvalidAndDuplicateCodesWhenApiReturnsThem(_sleep):
    manager = StockListManager()
    manager.session.get = MagicMock(return_value=make_response(4, [
        item('005930', '삼성전자'),
        item('005930', '삼성전자'),
        item('ABC', '잘못된코드'),
        item('000660', ''),
    ]))

    stocks = manager.scrape_market_stocks('KOSDAQ')

    assert stocks == [{'종목코드': '005930', '종목명': '삼성전자', '시장': 'KOSDAQ'}]


@patch.object(stock_list_manual.time, 'sleep')
def test_shouldStopPagingWhenPageIsEmpty(_sleep):
    manager = StockListManager()
    manager.session.get = MagicMock(return_value=make_response(500, []))

    manager.scrape_market_stocks('KOSPI')

    assert manager.session.get.call_count == 1
