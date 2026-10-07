# ROE 컬럼 동적 탐색 개선 plan

## 목표
`stock_roe_analyzer_final.py`의 `find_roe_dynamic_year()` 메서드에서
하드코딩된 컬럼 인덱스(`target_column_idx = 4`)를
헤더에서 `target_year` 문자열을 포함하는 컬럼을 동적으로 탐색하는 방식으로 교체한다.

---

## 테스트 목록

- [x] 헤더에 target_year가 포함된 컬럼 인덱스를 반환한다
- [x] 헤더에 target_year가 없으면 None을 반환한다
- [x] 여러 연도 컬럼 중 target_year와 일치하는 컬럼만 선택한다
- [x] 찾은 컬럼 인덱스로 ROE 값을 올바르게 추출한다
- [x] target_year가 포함된 컬럼이 없으면 ROE를 0.0으로 반환한다

---

# 종목 리스트 수집 소스 교체 plan

## 목표
네이버 금융 `sise_market_sum.nhn` 페이지가 `stock.naver.com`(SPA)으로 리다이렉트되어
HTML 테이블 스크래핑이 실패(종목 0개)하므로, `stock_list_manual.py`가
`m.stock.naver.com/api/stocks/marketValue/{KOSPI|KOSDAQ}` JSON API를 사용하도록 교체한다.

## 테스트 목록

- [x] 네이버 API가 응답하면 KOSPI/KOSDAQ 종목을 합쳐 반환한다 (API 레벨, 결함 재현)
- [x] totalCount가 pageSize보다 크면 모든 페이지를 가져온다
- [x] 6자리 숫자가 아닌 코드, 빈 종목명, 중복 코드는 건너뛴다
- [x] 빈 페이지를 만나면 페이징을 중단한다

---

# FnGuide 신버전 재무 API 전환 plan

## 목표
FnGuide 구버전 페이지(`comp.fnguide.com/SVO2/ASP/SVD_Main.asp`)가 폐지되어 "페이지가 없습니다" 안내만 반환하므로
(모든 종목 ROE 0%), `stock_roe_analyzer_final.py`가 신버전 재무 API
(`wcomp.fnguide.com/CompanyInfo/getSnpFinancial?cmp_cd=...&consol_typ=C&freq_typ=A`)에서 ROE를 읽도록 교체한다.

## 테스트 목록

- [x] FnGuide 재무 API가 응답하면 목표 연도 ROE를 반환한다 (API 레벨, 결함 재현)
- [x] API 응답이 JSON이 아니면(ETF 등) ROE를 0.0으로 처리한다
- [x] 목표 연도 ROE 값이 null이면 0.0을 반환한다
- [x] 목표 연도 컬럼이 없으면 0.0을 반환한다

### 3단계 재무 데이터 수집 / 종목명 수정 (stock_fundamentals_fetcher.py, fix_broken_names.py)

- [x] Snapshot HTML + 재무 API가 응답하면 자본총계·총주식수·예상ROE를 반환한다 (API 레벨, 결함 재현)
- [x] 자사주 행 라벨이 '자사주(자사주+자사주신탁)'여도 자기주식 수를 반환한다
- [x] 비12월 결산 종목은 최신 실적 연도의 자본총계(지배)를 반환한다
- [x] 마지막 추정 연도 순이익이 null이면 예상ROE 0.0을 반환한다
- [x] Snapshot 페이지의 #giName 에서 종목명을 반환한다
