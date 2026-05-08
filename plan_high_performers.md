# ROEHighPerformersFull 테스트 추가 및 리팩토링 plan

## 목표
`roe_high_performers_full.py`에 테스트를 추가하고,
외부 HTTP 의존성을 분리하여 테스트 가능한 구조로 리팩토링한다.

## 현재 문제점
- `find_high_roe_stocks()`가 실제 HTTP 요청을 하는 `StockROEAnalyzerFinal`에 직접 결합
- 통계 계산(평균/최대/최소)이 `print_results()` 안에 숨어 있어 테스트 불가
- ROE 구간 분포 계산 로직도 출력 함수 안에 매몰

## 리팩토링 방향
1. `StockROEAnalyzerFinal`을 생성자 주입으로 분리 → 테스트 시 mock으로 교체 가능
2. `filter_by_threshold()` — 필터링 로직 추출 (순수 함수)
3. `compute_stats()` — 통계 계산 추출 (순수 함수)
4. `compute_roe_distribution()` — 구간 분포 추출 (순수 함수)

## 테스트 목록

- [ ] ROE 임계값 이상인 종목만 반환한다
- [ ] ROE 기준 내림차순 정렬된 결과를 반환한다
- [ ] 임계값 이상인 종목이 없으면 빈 DataFrame을 반환한다
- [ ] 분석 결과가 없으면 빈 DataFrame을 반환한다
- [ ] 통계(평균/최대/최소)를 올바르게 계산한다
- [ ] ROE 구간별 분포를 올바르게 계산한다
