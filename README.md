# 주식 ROE 분석기

이 프로젝트는 pykrx 라이브러리를 사용하여 KOSPI와 KOSDAQ 종목 리스트를 가져오고, FnGuide 사이트에서 각 종목의 ROE(자기자본이익률) 값을 스크래핑하여 특정 임계값보다 높은 종목들을 찾는 Python 프로그램입니다.

## 최신 업데이트

- **Requests 기반 최종 버전**: Selenium/ChromeDriver 없이 requests만 사용
- **간소화된 의존성**: selenium, webdriver-manager 제거
- **향상된 안정성**: 더 빠르고 안정적인 스크래핑
- **SSL 경고 해결**: urllib3 버전 다운그레이드로 경고 제거
- **최종 파일 정리**: 핵심 파일만 유지

## 기능

- KOSPI와 KOSDAQ 전체 종목 리스트 자동 수집
- FnGuide 사이트에서 각 종목의 ROE 값 자동 스크래핑
- 설정한 임계값보다 ROE가 높은 종목 필터링
- 결과를 CSV 및 JSON 형식으로 저장
- 상세한 로깅 및 진행 상황 표시

## 설치 방법

### 1. 필요한 라이브러리 설치

```bash
pip install -r requirements.txt
```

### 2. Chrome 브라우저 설치

Selenium WebDriver가 Chrome을 사용하므로 Chrome 브라우저가 설치되어 있어야 합니다.

## 사용 방법

### 기본 사용법

```python
from stock_roe_analyzer_simple import SimpleStockROEAnalyzer

# 분석기 생성
analyzer = SimpleStockROEAnalyzer()

# ROE 10% 초과 종목 찾기
results = analyzer.analyze_stocks_by_roe(threshold=10.0, max_stocks=50)

# 결과 출력
print(results)

# 결과 저장
analyzer.save_results(results, "roe_results.csv")
```

### 직접 실행

```bash
# 전체 stock list 생성
python stock_list_manual.py

# roe 계산 (10% 이상만)
python roe_high_performers_full.py
```

## 매개변수 설명

- `threshold`: ROE 임계값 (기본값: 10.0)
- `max_stocks`: 분석할 최대 종목 수 (None이면 전체 종목)
- `use_api`: API 방식 사용 여부 (개선된 버전에서만)

## 출력 파일

- `roe_analysis_results.csv`: CSV 형식의 결과
- `roe_analysis_results.json`: JSON 형식의 결과

## 결과 예시

```
=== ROE 분석 결과 ===
ROE 10% 초과 종목: 3개

============================================================
종목코드    종목명    시장    ROE(%)
005930   삼성전자   KOSPI    17.05
000660   SK하이닉스  KOSPI    15.23
035420   NAVER     KOSPI    12.45
============================================================
```

## 주의사항

1. **서버 부하 방지**: 각 종목 분석 사이에 1-1.5초의 대기 시간을 두어 서버에 과부하를 주지 않도록 했습니다.

2. **네트워크 안정성**: 인터넷 연결이 안정적이어야 하며, FnGuide 사이트에 접근할 수 있어야 합니다.

3. **Chrome 브라우저**: Selenium WebDriver가 Chrome을 사용하므로 Chrome이 설치되어 있어야 합니다.

4. **실행 시간**: 전체 종목을 분석할 경우 상당한 시간이 소요될 수 있습니다.

## 문제 해결

### SSL 경고 해결
```bash
# urllib3 다운그레이드 (SSL 경고 해결)
python3 -m pip install urllib3==1.26.18 requests==2.28.2
```

### matplotlib 모듈 오류
```bash
# matplotlib 설치
python3 -m pip install matplotlib numpy
```

### 네트워크 연결 오류
- 인터넷 연결 상태를 확인하세요
- 방화벽이나 프록시 설정을 확인하세요

### 네트워크 타임아웃
- 인터넷 연결 상태를 확인하세요
- 방화벽이나 프록시 설정을 확인하세요

### ROE 값을 찾을 수 없는 경우
- 해당 종목의 재무제표가 FnGuide에 업데이트되지 않았을 수 있습니다
- 일부 신규 상장 종목은 데이터가 없을 수 있습니다

## 라이센스

이 프로젝트는 교육 및 개인 연구 목적으로만 사용하시기 바랍니다. 상업적 사용 시 관련 법규를 준수해주세요.

## 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요. 




  변경 요약

  ┌───────────────────┬───────────────────────────────────────────────────────────────────────────────┐
  │       파일        │                                   변경 내용                                   │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ s_rim.py          │ SRIMCalculator 클래스 추가 — proper_price(), conservative_price(), calc_row() │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ s_rim_pipeline.py │ 신설 — merge_inputs(), SRIMPipeline, CLI 진입점                               │
  ├───────────────────┼───────────────────────────────────────────────────────────────────────────────┤
  │ test_s_rim.py     │ 신설 — 6개 테스트                                                             │
  └───────────────────┴───────────────────────────────────────────────────────────────────────────────┘

  다음 단계: 재무 데이터 URL을 주시면 stock_fundamentals_fetcher.py 스크래핑 로직을 구현합니다.


```bash
# 1단계: 종목 코드 생성
python stock_list_manual.py

# 2단계: roe 계산 (10% 이상만)
python roe_high_performers_full.py

# 3단계: 재무 데이터 수집 (ROE CSV → fundamentals CSV)
python stock_fundamentals_fetcher.py \
  --roe-csv roe_10.0plus_2026_full_results.csv \
  --output fundamentals_2026.csv

# 4단계: S-RIM 적정 주가 계산
python s_rim_pipeline.py \
  --roe-csv roe_10.0plus_2026_full_results.csv \
  --fundamentals-csv fundamentals_2026.csv
```


수정 요약

  ┌──────────────────────────────────┬────────────────────────────────────────┬────────────────────────────────────────────────────────────┐
  │               버그               │                  원인                  │                            수정                            │
  ├──────────────────────────────────┼────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 950170: 지배주주지분 찾지 못함   │ 2025/12만 탐색, 비12월 회계연도 미지원 │ Annual colspan으로 섹션 경계 파악 → 마지막 YYYY/MM 셀 사용 │
  ├──────────────────────────────────┼────────────────────────────────────────┼────────────────────────────────────────────────────────────┤
  │ 자기주식을 찾지 못했습니다 (4회) │ 자기주식 없는 종목도 경고 출력         │ 자기주식 없으면 0 반환, 경고 제거                          │
  └──────────────────────────────────┴────────────────────────────────────────┴────────────────────────────────────────────────────────────┘


```bash
# 종목명 한글이 깨질 경우 fix
python fix_broken_names.py <파일명>
```