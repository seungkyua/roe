# S-RIM 파이프라인 구현 plan

## 테스트 목록

### SRIMCalculator (s_rim.py)
- [ ] proper_price()가 기본 S-RIM 공식으로 적정 주가를 반환한다
- [ ] conservative_price()가 초과이익 10% 감소 모델로 보수적 주가를 반환한다
- [ ] calc_row()가 dict 입력을 받아 두 가지 주가를 추가한 dict를 반환한다

### SRIMPipeline (s_rim_pipeline.py)
- [ ] merge_inputs()가 두 DataFrame을 종목코드 기준 inner join으로 병합한다
- [ ] merge_inputs()가 한쪽에만 있는 종목은 제외한다
- [ ] SRIMPipeline.run()이 병합 데이터에 S-RIM 계산을 적용한 결과를 반환한다
