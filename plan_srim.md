# S-RIM 파이프라인 구현 plan

## 테스트 목록

### SRIMCalculator (s_rim.py)
- [x] proper_price()가 기본 S-RIM 공식으로 적정 주가를 반환한다
- [x] conservative_price()가 초과이익 10% 감소 모델로 보수적 주가를 반환한다
- [x] calc_row()가 dict 입력을 받아 두 가지 주가를 추가한 dict를 반환한다

### SRIMPipeline (s_rim_pipeline.py)
- [x] merge_inputs()가 두 DataFrame을 종목코드 기준 inner join으로 병합한다
- [x] merge_inputs()가 한쪽에만 있는 종목은 제외한다
- [x] SRIMPipeline.run()이 병합 데이터에 S-RIM 계산을 적용한 결과를 반환한다

### StockFundamentalsFetcher (stock_fundamentals_fetcher.py)
- [ ] find_equity()가 Financial Highlight 표에서 작년 12월 지배주주지분을 원 단위로 반환한다
- [ ] find_issued_shares()가 시세현황 표에서 보통주 발행주식수를 반환한다
- [ ] find_treasury_shares()가 주주구분 현황 표에서 자기주식 보통주를 반환한다
- [ ] fetch()가 종목코드로 페이지를 가져와 자본총계(원)과 총주식수를 반환한다
