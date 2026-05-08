#!/usr/bin/env python3
"""
깨진 종목명을 FnGuide에서 올바른 이름으로 교체.
대상 파일: srim_results_*.csv, roe_*.csv, fundamentals_*.csv
"""

import re
import time
import logging
import argparse
import pandas as pd
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FNGUIDE_URL = (
    "https://comp.fnguide.com/SVO2/ASP/SVD_Main.asp"
    "?pGB=1&gicode=A{code}&cID=&MenuYn=Y&ReportGB=&NewMenuID=11&stkGb=701"
)

# 한글/영문/숫자/일반 기호 외 문자가 포함된 이름을 "깨진 이름"으로 판별
_BROKEN_PATTERN = re.compile(r'[^가-힣ᄀ-ᇿ㄰-㆏\w\s\(\)\.\-&\+\'\"\/]')


def is_broken(name: str) -> bool:
    return bool(_BROKEN_PATTERN.search(str(name)))


def fetch_name_from_fnguide(stock_code: str, session: requests.Session) -> str:
    """FnGuide #giName 요소에서 종목명 가져오기"""
    try:
        url = FNGUIDE_URL.format(code=stock_code)
        resp = session.get(url, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        el = soup.select_one('#giName')
        if el:
            name = el.get_text(strip=True)
            if name:
                return name
    except Exception as e:
        logger.warning(f"{stock_code} FnGuide 조회 실패: {e}")
    return ''


def fix_csv(filepath: str, max_workers: int = 5) -> int:
    """CSV 파일에서 깨진 종목명을 FnGuide에서 가져온 이름으로 교체. 수정된 행 수 반환."""
    df = pd.read_csv(filepath, encoding='utf-8-sig', dtype={'종목코드': str})
    if '종목명' not in df.columns:
        logger.info(f"{filepath}: 종목명 컬럼 없음, 건너뜀")
        return 0

    broken_mask = df['종목명'].apply(is_broken)
    broken_df = df[broken_mask]
    if broken_df.empty:
        logger.info(f"{filepath}: 깨진 이름 없음")
        return 0

    logger.info(f"{filepath}: 깨진 이름 {len(broken_df)}개 수정 시작")

    session = requests.Session()
    session.headers.update({
        'User-Agent': (
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        'Accept-Language': 'ko-KR,ko;q=0.9',
    })

    fixed = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_name_from_fnguide, row['종목코드'], session): row['종목코드']
            for _, row in broken_df.iterrows()
        }
        for future in as_completed(futures):
            code = futures[future]
            name = future.result()
            if name:
                fixed[code] = name
                logger.info(f"  {code}: '{df.loc[df['종목코드']==code, '종목명'].iloc[0]}' → '{name}'")
            else:
                logger.warning(f"  {code}: 이름을 가져오지 못했습니다")

    # 수정 적용
    for code, name in fixed.items():
        df.loc[df['종목코드'] == code, '종목명'] = name

    df.to_csv(filepath, index=False, encoding='utf-8-sig')
    logger.info(f"{filepath}: {len(fixed)}개 수정 완료")
    return len(fixed)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='깨진 종목명 수정')
    parser.add_argument('files', nargs='+', help='수정할 CSV 파일 경로')
    parser.add_argument('--workers', type=int, default=5)
    args = parser.parse_args()

    total = 0
    for f in args.files:
        if not Path(f).exists():
            logger.warning(f"파일 없음: {f}")
            continue
        total += fix_csv(f, max_workers=args.workers)

    print(f"\n총 {total}개 종목명 수정 완료")
