def round_to(num):
    return round(num / 10) * 10


def s_rim():
    # =============================================================================
    # 원택
    # =============================================================================
    # 자본 총계
    equity = 151300000000   # 테스트
    equity = 126800000000   # 원텍

    # ROE (금년도 예상 ROE)
    roe = 15.22    # 테스트
    roe = 31.95    # 원텍

    # ROE (금년도 예상 roe 가 없을 때)
    # roe = ((7.65 * 3) + (8.96 * 2) + (6.79 * 1)) / 6

    # 이익 할인율 (BBB- 5년 회사채 금리)
    discount_rate = 8.05    # 테스트
    discount_rate = 9.24    # 9.24%

    # 총 주식수 = 발행 주식수(보통주) - 자기 주식(보통주)
    total_shares = 15179843              # 테스트
    total_shares = 89968897 - 3793       # 원텍

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('===== 원택 ====== \n' +
          f'적정 주가 = {proper_values} \n'  +
          f'10% 하락 주가 = {proper_values_1} ')

    # ROE 컨센선스 (지배주주순이익 / 지배주주지분(평균))
    roe = 60200000000 / ((273600000000 + 216200000000) / 2) * 100    # 원택

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('---- 원택 (컨센선스) ---- \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} \n')

    # =============================================================================
    # 아세아시멘트
    # =============================================================================
    # 자본 총계
    equity = 1094000000000  # 아세아시멘트

    # ROE (금년도 예상 ROE)
    roe = 4.42  # 아세아시멘트

    # ROE (금년도 예상 roe 가 없을 때)
    # roe = ((7.65 * 3) + (8.96 * 2) + (6.79 * 1)) / 6

    # 이익 할인율 (BBB- 5년 회사채 금리)
    discount_rate = 9.24  # 9.24%

    # 총 주식수 = 발행 주식수(보통주) - 자기 주식(보통주)
    total_shares = 37346770 - 959708  # 아세아시멘트

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('===== 아세아시멘트 ====== \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} ')


    # ROE 컨센선스 (지배주주순이익 / 지배주주지분(평균))
    roe = 71000000000 / ((1237000000000 + 1175000000000) / 2) * 100  # 아세아시멘트

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('---- 아세아시멘트 (컨센선스) ---- \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} \n')


    #=============================================================================
    # 삼성물산
    # =============================================================================
    # 자본 총계
    equity = 31068700000000  # 삼성물산

    # ROE (금년도 예상 ROE)
    roe = 6.67  # 삼성물산

    # ROE (금년도 예상 roe 가 없을 때)
    # roe = ((7.65 * 3) + (8.96 * 2) + (6.79 * 1)) / 6

    # 이익 할인율 (BBB- 5년 회사채 금리)
    discount_rate = 9.24  # 9.24%

    # 총 주식수 = 발행 주식수(보통주) - 자기 주식(보통주)
    total_shares = 169976544 - 7808963  # 삼성물산

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('===== 삼성물산 ====== \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} ')

    # ROE 컨센선스 (지배주주순이익 / 지배주주지분(평균))
    roe = 2627200000000 / ((39638700000000 + 36459400000000) / 2) * 100  # 삼성물산

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('---- 삼성물산 (컨센선스) ---- \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} \n')

    # =============================================================================
    # Naver
    # =============================================================================
    # 자본 총계 (지배주주지분)
    equity = 25459900000000  # Naver

    # ROE (금년도 예상 ROE)
    roe = 7.17  # Naver

    # ROE (금년도 예상 roe 가 없을 때)
    # roe = ((7.65 * 3) + (8.96 * 2) + (6.79 * 1)) / 6

    # 이익 할인율 (BBB- 5년 회사채 금리)
    discount_rate = 9.24  # 9.24%

    # 총 주식수 = 발행 주식수(보통주) - 자기 주식(보통주)
    total_shares = 158437008 - 9147937  # Naver

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('===== Naver ====== \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} ')

    # ROE 컨센선스 (지배주주순이익 / 지배주주지분(평균))
    roe = 2461000000000 / ((32522900000000 + 29915300000000) / 2) * 100  # Naver

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('---- Naver (컨센선스) ---- \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} \n')

    # =============================================================================
    # 제닉
    # =============================================================================
    # 자본 총계 (지배주주지분)
    equity = 22200000000

    # ROE (금년도 예상 ROE)
    roe = 78.01

    # ROE (금년도 예상 roe 가 없을 때)
    # roe = ((7.65 * 3) + (8.96 * 2) + (6.79 * 1)) / 6

    # 이익 할인율 (BBB- 5년 회사채 금리)
    discount_rate = 9.24

    # 총 주식수 = 발행 주식수(보통주) - 자기 주식(보통주)
    total_shares = 7968680 - 143994

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('===== 제닉 ====== \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} ')

    # ROE 컨센선스 (지배주주순이익 / 지배주주지분(평균))
    roe = 38500000000 / ((88900000000 + 50400000000) / 2) * 100  # Naver

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('---- 제닉 (컨센선스) ---- \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} \n')

    # =============================================================================
    # 선익시스템
    # =============================================================================
    # 자본 총계 (지배주주지분)
    equity = 46400000000

    # ROE (금년도 예상 ROE)
    roe = 66.75

    # ROE (금년도 예상 roe 가 없을 때)
    # roe = ((7.65 * 3) + (8.96 * 2) + (6.79 * 1)) / 6

    # 이익 할인율 (BBB- 5년 회사채 금리)
    discount_rate = 9.24

    # 총 주식수 = 발행 주식수(보통주) - 자기 주식(보통주)
    total_shares = 9558504 - 739004

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('===== 선익시스템 ====== \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} ')

    # ROE 컨센선스 (지배주주순이익 / 지배주주지분(평균))
    roe = 90400000000 / ((250700000000 + 160300000000) / 2) * 100  # Naver

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('---- 선익시스템 (컨센선스) ---- \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} \n')

    # =============================================================================
    # 아스테라시스
    # =============================================================================
    # 자본 총계 (지배주주지분)
    equity = 19600000000

    # ROE (금년도 예상 ROE)
    roe = 51.05

    # ROE (금년도 예상 roe 가 없을 때)
    # roe = ((7.65 * 3) + (8.96 * 2) + (6.79 * 1)) / 6

    # 이익 할인율 (BBB- 5년 회사채 금리)
    discount_rate = 9.24

    # 총 주식수 = 발행 주식수(보통주) - 자기 주식(보통주)
    total_shares = 37407092 - 0

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('===== 아스테라시스 ====== \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} ')

    # ROE 컨센선스 (지배주주순이익 / 지배주주지분(평균))
    roe = 30100000000 / ((83800000000 + 60900000000) / 2) * 100  # Naver

    _, proper_values = cal_proper_values(discount_rate, equity, roe, total_shares)
    proper_values_1 = cal_supernormal_values(discount_rate, equity, roe, total_shares)

    print('---- 아스테라시스 (컨센선스) ---- \n' +
          f'적정 주가 = {proper_values} \n' +
          f'10% 하락 주가 = {proper_values_1} \n')


def cal_supernormal_values(discount_rate, equity, roe, total_shares):
    # 초과 이익
    supernormal_profit = equity * (roe - discount_rate) / 100

    # 초과 이익 연 10% 이상씩 하락
    year_rate = -0.1
    company_values_1 = equity + (supernormal_profit * (1 + year_rate) / (1 + (discount_rate / 100) - (1 + year_rate)))
    proper_values_1 = company_values_1 / total_shares
    return round_to(proper_values_1)


def cal_proper_values(discount_rate, equity, roe, total_shares):
    # 기업 가치
    company_values = equity + (equity * (roe - discount_rate)) / discount_rate

    # 적정 추가
    proper_values = company_values / total_shares
    return round_to(company_values), round_to(proper_values)


class SRIMCalculator:
    def __init__(self, discount_rate: float):
        self.discount_rate = discount_rate

    def proper_price(self, equity: float, roe: float, total_shares: int) -> float:
        _, price = cal_proper_values(self.discount_rate, equity, roe, total_shares)
        return price

    def conservative_price(self, equity: float, roe: float, total_shares: int) -> float:
        return cal_supernormal_values(self.discount_rate, equity, roe, total_shares)

    def calc_row(self, row: dict) -> dict:
        equity = row['자본총계(원)']
        roe = row['ROE(%)']
        total_shares = row['총주식수']
        return {
            **row,
            '적정주가(S-RIM)': self.proper_price(equity, roe, total_shares),
            '보수적주가(S-RIM)': self.conservative_price(equity, roe, total_shares),
        }


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    s_rim()
