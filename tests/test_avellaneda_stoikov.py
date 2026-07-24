import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.policies.avellaneda_stoikov import AvellanedaStoikovPolicy, AvellanedaStoikovParams


def make_policy(**overrides):
    params = AvellanedaStoikovParams(**overrides) if overrides else AvellanedaStoikovParams()
    return AvellanedaStoikovPolicy(params)


def test_reservation_price_equals_mid_when_inventory_zero():
    """r(s,t) = s - q*gamma*sigma^2*(T-t); at q=0 the inventory term vanishes
    regardless of gamma, sigma, or time remaining."""
    policy = make_policy()
    reservation, bid, ask, spread, _ = policy._compute_quotes(
        mid_price=350.0, inventory_kg=0.0, t=0.0, T=1.0, sigma=0.35
    )
    assert reservation == pytest.approx(350.0)
    assert ask > reservation > bid  # spread still applies even with q=0


def test_higher_inventory_lowers_reservation_price():
    """Core mastery-checkpoint property: excess inventory should lower the
    reservation price (dealer becomes more willing to sell it off)."""
    policy = make_policy()
    r_low_inv, *_ = policy._compute_quotes(mid_price=350.0, inventory_kg=10.0, t=0.0, T=1.0, sigma=0.35)
    r_high_inv, *_ = policy._compute_quotes(mid_price=350.0, inventory_kg=300.0, t=0.0, T=1.0, sigma=0.35)
    assert r_high_inv < r_low_inv


def test_negative_inventory_would_raise_reservation_price():
    """Sanity check on the formula's symmetry: a hypothetical short position
    (q < 0) should raise the reservation price above mid, confirming the
    sign convention is q * gamma * sigma^2 * (T-t) subtracted from mid, not added."""
    policy = make_policy()
    reservation, *_ = policy._compute_quotes(mid_price=350.0, inventory_kg=-50.0, t=0.0, T=1.0, sigma=0.35)
    assert reservation > 350.0


def test_risk_aversion_strengthens_inventory_adjustment():
    """Higher gamma -> larger reservation-price shift for the same inventory,
    time remaining, and volatility."""
    low_gamma_policy = make_policy(risk_aversion=1e-6)
    high_gamma_policy = make_policy(risk_aversion=1e-5)

    r_low, *_ = low_gamma_policy._compute_quotes(mid_price=350.0, inventory_kg=200.0, t=0.0, T=1.0, sigma=0.35)
    r_high, *_ = high_gamma_policy._compute_quotes(mid_price=350.0, inventory_kg=200.0, t=0.0, T=1.0, sigma=0.35)

    shift_low = abs(350.0 - r_low)
    shift_high = abs(350.0 - r_high)
    assert shift_high > shift_low


def test_inventory_adjustment_shrinks_near_end_of_horizon():
    """Mastery checkpoint: as t -> T, (T-t) -> 0, so the inventory-risk term
    vanishes and the reservation price converges back toward mid price."""
    policy = make_policy()
    r_early, *_ = policy._compute_quotes(mid_price=350.0, inventory_kg=200.0, t=0.0, T=1.0, sigma=0.35)
    r_late, *_ = policy._compute_quotes(mid_price=350.0, inventory_kg=200.0, t=0.999, T=1.0, sigma=0.35)

    shift_early = abs(350.0 - r_early)
    shift_late = abs(350.0 - r_late)
    assert shift_late < shift_early
    assert r_late == pytest.approx(350.0, abs=1.0)  # nearly fully collapsed near horizon end


def test_spread_widens_with_higher_volatility():
    """Higher sigma should widen the total quoted spread (both the
    inventory-risk term and, via sigma_abs, the reservation shift magnitude)."""
    policy = make_policy()
    _, _, _, spread_low, _ = policy._compute_quotes(mid_price=350.0, inventory_kg=100.0, t=0.0, T=1.0, sigma=0.10)
    _, _, _, spread_high, _ = policy._compute_quotes(mid_price=350.0, inventory_kg=100.0, t=0.0, T=1.0, sigma=0.60)
    assert spread_high > spread_low


def test_spread_does_not_fully_collapse_at_horizon_end():
    """Mastery checkpoint: the order-flow term (2/gamma)*ln(1+gamma/k) is
    independent of time remaining and should keep the spread positive even
    exactly at t = T."""
    policy = make_policy()
    _, _, _, spread_at_horizon, time_remaining = policy._compute_quotes(
        mid_price=350.0, inventory_kg=0.0, t=1.0, T=1.0, sigma=0.35
    )
    assert time_remaining == 0.0
    assert spread_at_horizon > 0.0


def test_ask_and_bid_straddle_reservation_price_symmetrically():
    policy = make_policy()
    reservation, bid, ask, spread, _ = policy._compute_quotes(
        mid_price=350.0, inventory_kg=150.0, t=0.2, T=1.0, sigma=0.35
    )
    assert ask - reservation == pytest.approx(reservation - bid)
    assert ask - bid == pytest.approx(spread)


def test_quote_ask_matches_compute_quotes_ask_and_records_diagnostics():
    policy = make_policy()
    ask = policy.quote_ask(mid_price=350.0, inventory_kg=120.0, t=0.1, T=1.0, sigma=0.35)
    _, _, expected_ask, _, _ = policy._compute_quotes(
        mid_price=350.0, inventory_kg=120.0, t=0.1, T=1.0, sigma=0.35
    )
    assert ask == pytest.approx(expected_ask)
    assert policy.last_diagnostics["ask"] == pytest.approx(ask)
    assert policy.last_diagnostics["inventory_kg"] == 120.0


def test_invalid_params_raise():
    with pytest.raises(ValueError):
        AvellanedaStoikovPolicy(AvellanedaStoikovParams(risk_aversion=0.0))
    with pytest.raises(ValueError):
        AvellanedaStoikovPolicy(AvellanedaStoikovParams(k=0.0))
