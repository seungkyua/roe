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
