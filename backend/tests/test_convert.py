from datetime import date

import pytest

from spotwise.convert import (
    TaxProfile,
    TaxRule,
    apply_tax,
    pct_move,
    per_gram,
    spot_per_gram,
)


def test_vector_gold_inr():
    # gold 1824.0852 USD/toz, INR 0.012082 USD/unit -> about 4854 INR/g spot
    assert spot_per_gram(1824.0852, 0.012082) == pytest.approx(4854, abs=1)


def test_vector_gold_aed():
    # gold 1926.81 USD/toz, AED 0.27225333 USD/unit -> about 227.5 AED/g spot
    assert spot_per_gram(1926.81, 0.27225333) == pytest.approx(227.5, abs=0.1)


def test_purity_22k():
    full = spot_per_gram(1824.0852, 0.012082, 1.0)
    assert spot_per_gram(1824.0852, 0.012082, 0.916) == pytest.approx(full * 0.916)


def test_tax_order_duty_then_premium_then_gst():
    rule = TaxRule(date(2026, 1, 1), duty_pct=6, premium_per_gram=10, gst_pct=3)
    # (1000 * 1.06 + 10) * 1.03
    assert apply_tax(1000, rule) == pytest.approx((1000 * 1.06 + 10) * 1.03)


def test_no_rule_means_no_tax():
    assert apply_tax(1000, None) == 1000


def test_effective_dating_picks_latest_applicable_rule():
    profile = TaxProfile(
        rules=[
            TaxRule(date(2020, 1, 1), duty_pct=10, gst_pct=3),
            TaxRule(date(2024, 7, 23), duty_pct=6, gst_pct=3),
        ]
    )
    assert profile.rule_for(date(2019, 1, 1)) is None
    assert profile.rule_for(date(2023, 1, 1)).duty_pct == 10
    assert profile.rule_for(date(2024, 7, 23)).duty_pct == 6
    assert profile.rule_for(date(2026, 1, 1)).duty_pct == 6


def test_per_gram_applies_profile_by_date():
    profile = TaxProfile(
        rules=[
            TaxRule(date(2020, 1, 1), duty_pct=10),
            TaxRule(date(2024, 1, 1), duty_pct=5),
        ]
    )
    old = per_gram(1824.0852, 0.012082, on=date(2021, 5, 1), profile=profile)
    new = per_gram(1824.0852, 0.012082, on=date(2025, 5, 1), profile=profile)
    spot = spot_per_gram(1824.0852, 0.012082)
    assert old == pytest.approx(spot * 1.10)
    assert new == pytest.approx(spot * 1.05)


def test_percent_move_is_metal_times_currency():
    # Tax, duty and purity cancel out of percent moves; only metal and FX matter.
    metal_old, metal_new = 1800.0, 1890.0
    fx_old, fx_new = 0.0120, 0.0115  # INR weakened
    a = spot_per_gram(metal_old, fx_old)
    b = spot_per_gram(metal_new, fx_new)
    expected = ((metal_new / metal_old) / (fx_new / fx_old) - 1) * 100
    assert pct_move(a, b) == pytest.approx(expected)


def test_rejects_nonpositive_inputs():
    with pytest.raises(ValueError):
        spot_per_gram(0, 0.012)
    with pytest.raises(ValueError):
        spot_per_gram(1800, 0)
