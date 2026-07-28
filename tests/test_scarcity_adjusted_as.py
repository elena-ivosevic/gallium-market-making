import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.policies.scarcity_adjusted_as import ScarcityAdjustedASPolicy, ScarcityAdjustedASParams


def make_policy(**overrides):
    params = ScarcityAdjustedASParams(**overrides) if overrides else ScarcityAdjustedASParams()
    return ScarcityAdjustedASPolicy(params)


def test_all_premiums_zero_outside_supply_chain_regime_state():
    """With no available_kg/reliability/etc supplied, every premium should
    evaluate to zero -- this policy degrades to plain AS behavior."""
    policy = make_policy()
    ask = policy.quote_ask(mid_price=350.0, inventory_kg=100.0, t=0.0, T=1.0, sigma=0.35)
    diag = policy.last_diagnostics
    assert diag["scarcity_premium"] == 0.0
    assert diag["replacement_cost_premium"] == 0.0
    assert diag["shipment_risk_premium"] == 0.0
    assert diag["commitment_premium"] == 0.0
    assert diag["regime_premium"] == 0.0
    assert diag["reservation_price"] == pytest.approx(diag["base_reservation_price"])


def test_scarcity_premium_increases_as_available_kg_falls():
    policy = make_policy()
    _ = policy.quote_ask(mid_price=350.0, inventory_kg=100.0, available_kg=100.0, safety_stock_kg=60.0)
    high_avail_premium = policy.last_diagnostics["scarcity_premium"]
    _ = policy.quote_ask(mid_price=350.0, inventory_kg=100.0, available_kg=-30.0, safety_stock_kg=60.0)
    low_avail_premium = policy.last_diagnostics["scarcity_premium"]
    assert low_avail_premium > high_avail_premium
    assert high_avail_premium == 0.0  # available >= safety_stock -> no shortfall


def test_scarcity_premium_caps_at_gamma_times_mid_price():
    policy = make_policy(scarcity_gamma=0.05)
    _ = policy.quote_ask(mid_price=350.0, available_kg=-10_000.0, safety_stock_kg=60.0)
    premium = policy.last_diagnostics["scarcity_premium"]
    assert premium == pytest.approx(350.0 * 0.05, abs=1e-6)  # capped, not unbounded


def test_replacement_cost_premium_only_reflects_excess_above_base_markup():
    policy = make_policy(replacement_cost_pass_through=0.15, replacement_cost_base_markup=0.03)
    _ = policy.quote_ask(mid_price=350.0, replacement_markup_frac=0.03)  # exactly base -> no excess
    assert policy.last_diagnostics["replacement_cost_premium"] == pytest.approx(0.0)

    _ = policy.quote_ask(mid_price=350.0, replacement_markup_frac=0.23)  # 20pp excess
    expected = 350.0 * 0.15 * (0.23 - 0.03)
    assert policy.last_diagnostics["replacement_cost_premium"] == pytest.approx(expected)


def test_shipment_risk_premium_increases_as_reliability_falls():
    policy = make_policy(shipment_risk_gamma=0.10)
    _ = policy.quote_ask(mid_price=350.0, civilian_reliability=0.95)
    high_rel_premium = policy.last_diagnostics["shipment_risk_premium"]
    _ = policy.quote_ask(mid_price=350.0, civilian_reliability=0.40)
    low_rel_premium = policy.last_diagnostics["shipment_risk_premium"]
    assert low_rel_premium > high_rel_premium
    assert high_rel_premium == pytest.approx(350.0 * 0.10 * 0.05)


def test_commitment_premium_increases_with_committed_kg_and_caps_at_3x():
    policy = make_policy(commitment_gamma=0.03)
    _ = policy.quote_ask(mid_price=350.0, committed_kg=0.0, safety_stock_kg=60.0)
    assert policy.last_diagnostics["commitment_premium"] == pytest.approx(0.0)

    _ = policy.quote_ask(mid_price=350.0, committed_kg=60.0, safety_stock_kg=60.0)
    at_one_x = policy.last_diagnostics["commitment_premium"]
    assert at_one_x == pytest.approx(350.0 * 0.03 * 1.0)

    _ = policy.quote_ask(mid_price=350.0, committed_kg=6000.0, safety_stock_kg=60.0)  # way over 3x
    capped = policy.last_diagnostics["commitment_premium"]
    assert capped == pytest.approx(350.0 * 0.03 * 3.0)  # capped, not unbounded


def test_regime_premium_scales_with_severity_and_is_clamped_to_unit_interval():
    policy = make_policy(regime_gamma=0.08)
    _ = policy.quote_ask(mid_price=350.0, regime_severity=0.0)
    assert policy.last_diagnostics["regime_premium"] == pytest.approx(0.0)
    _ = policy.quote_ask(mid_price=350.0, regime_severity=1.0)
    assert policy.last_diagnostics["regime_premium"] == pytest.approx(350.0 * 0.08)
    _ = policy.quote_ask(mid_price=350.0, regime_severity=5.0)  # out of range, should clamp
    assert policy.last_diagnostics["regime_premium"] == pytest.approx(350.0 * 0.08)


def test_premiums_never_negative_even_with_favorable_inputs():
    """All five premiums should floor at zero -- they only ever protect
    scarce inventory, never discount it further than plain AS already would."""
    policy = make_policy()
    _ = policy.quote_ask(
        mid_price=350.0, available_kg=10_000.0, safety_stock_kg=60.0,
        replacement_markup_frac=0.0, civilian_reliability=1.0,
        committed_kg=0.0, regime_severity=0.0,
    )
    diag = policy.last_diagnostics
    for key in ("scarcity_premium", "replacement_cost_premium", "shipment_risk_premium",
                "commitment_premium", "regime_premium"):
        assert diag[key] >= 0.0


def test_ask_rises_with_total_premium():
    policy = make_policy()
    ask_calm = policy.quote_ask(mid_price=350.0, inventory_kg=100.0, t=0.0, T=1.0, sigma=0.35)
    ask_stressed = policy.quote_ask(
        mid_price=350.0, inventory_kg=100.0, t=0.0, T=1.0, sigma=0.35,
        available_kg=-50.0, safety_stock_kg=60.0, replacement_markup_frac=0.5,
        civilian_reliability=0.3, committed_kg=200.0, regime_severity=1.0,
    )
    assert ask_stressed > ask_calm


def test_restock_markup_frac_inherited_from_avellaneda_stoikov():
    """ScarcityAdjustedASPolicy should reuse AS's restock_markup_frac
    interface method unchanged (inherited, not reimplemented)."""
    policy = make_policy(restock_markup_frac=0.04)
    assert policy.restock_markup_frac() == 0.04


def test_invalid_gamma_or_k_still_rejected_via_parent_validation():
    with pytest.raises(ValueError):
        ScarcityAdjustedASPolicy(ScarcityAdjustedASParams(risk_aversion=0.0))
