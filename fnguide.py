#!/usr/bin/env python3
"""
FnGuide 신버전(wcomp.fnguide.com) 공통 접근 모듈

구버전 페이지(comp.fnguide.com/SVO2/ASP/SVD_Main.asp)가 폐지되어
"페이지가 없습니다" 안내만 반환하므로 신버전 주소를 사용한다.
  - Snapshot HTML : 종목명(#giName), 시세현황(발행주식수), 주주구분 현황(자사주)
  - 재무 API      : Financial Highlight(연결) JSON — freq_typ 'A'(연간4+분기4) / 'Y'(연간8)
"""

import time
import logging

logger = logging.getLogger(__name__)

SNAPSHOT_URL = "https://wcomp.fnguide.com/CompanyInfo/Snapshot"
FINANCIAL_API = "https://wcomp.fnguide.com/CompanyInfo/getSnpFinancial"


def get_financial(session, stock_code, freq_typ='A', max_retries=3, retry_delay=5):
    """재무 하이라이트(연결) dataset 반환. 재무 데이터가 없는 종목(ETF 등)이거나 실패 시 None."""
    for attempt in range(max_retries):
        try:
            response = session.get(
                FINANCIAL_API,
                params={'cmp_cd': stock_code, 'consol_typ': 'C', 'freq_typ': freq_typ},
                timeout=15,
            )
            response.raise_for_status()
        except Exception as e:
            logger.warning(f"{stock_code} 재무 데이터 요청 실패 (시도 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))  # 지수적 백오프
            continue

        # ETF 등 재무 데이터가 없는 종목은 빈 응답(JSON 아님)이 오므로 재시도하지 않는다
        try:
            return response.json().get('dataset')
        except ValueError:
            logger.info(f"{stock_code} 재무 데이터 없음")
            return None

    logger.error(f"{stock_code} 재무 데이터 최대 재시도 횟수 초과")
    return None


def find_row(dataset, name):
    """dataset 에서 항목명(NAME, 앞뒤 공백 무시)이 name 인 행 반환. 없으면 None."""
    for row in dataset.get('data', []):
        if (row.get('NAME') or '').strip() == name:
            return row
    return None


def to_float(value):
    """API 값 문자열을 float 으로 변환. None/빈 값이면 None."""
    if value in (None, ''):
        return None
    return float(value)
