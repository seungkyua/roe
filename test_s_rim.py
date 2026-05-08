import pytest
import pandas as pd
from s_rim import SRIMCalculator
from s_rim_pipeline import merge_inputs, SRIMPipeline


# ── SRIMCalculator ────────────────────────────────────────────────────────────

def make_calc(discount_rate=9.24):
    return SRIMCalculator(discount_rate=discount_rate)


def test_proper_price_returns_srim_valuation():
    """기본 S-RIM: V = equity + equity*(ROE-r)/r, price = V / total_shares"""
    calc = make_calc(discount_rate=9.24)
    equity = 126_800_000_000
    roe = 31.95
    total_shares = 89_968_897 - 3_793

    price = calc.proper_price(equity, roe, total_shares)

    # cal_proper_values 직접 계산값과 일치해야 함
    from s_rim import cal_proper_values
    _, expected = cal_proper_values(9.24, equity, roe, total_shares)
    assert price == expected
