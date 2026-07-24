import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.policies.inventory_heuristic import InventoryHeuristicPolicy, InventoryHeuristicParams


def make_policy(**overrides):
    params = InventoryHeuristicParams(**overrides) if overrides else InventoryHeuristicParams()
    return InventoryHeuristicPolicy(params)


def test_normal_inventory_uses_base_spread():
    policy = make_policy(low_threshold_kg=80.0, high_threshold_kg=250.0, base_ask_spread_frac=0.04)
    ask = policy.quote_ask(mid_price=350.0, inventory_kg=150.0)
    assert ask == pytest.approx(350.0 * 1.04)
    assert policy.last_diagnostics["inventory_regime"] == "normal"


def test_low_inventory_raises_ask():
    policy = make_policy(low_threshold_kg=80.0, base_ask_spread_frac=0.04, low_inventory_extra_frac=0.03)
    ask = policy.quote_ask(mid_price=350.0, inventory_kg=50.0)
    assert ask == pytest.approx(350.0 * (1.0 + 0.04 + 0.03))
    assert policy.last_diagnostics["inventory_regime"] == "scarce"


def test_high_inventory_lowers_ask():
    policy = make_policy(high_threshold_kg=250.0, base_ask_spread_frac=0.04, high_inventory_discount_frac=0.02)
    ask = policy.quote_ask(mid_price=350.0, inventory_kg=300.0)
    assert ask == pytest.approx(350.0 * (1.0 + 0.04 - 0.02))
    assert policy.last_diagnostics["inventory_regime"] == "excess"


def test_thresholds_are_inclusive_at_the_boundary():
    policy = make_policy(low_threshold_kg=80.0, high_threshold_kg=250.0)
    ask_at_low = policy.quote_ask(mid_price=350.0, inventory_kg=80.0)
    assert policy.last_diagnostics["inventory_regime"] == "scarce"
    ask_at_high = policy.quote_ask(mid_price=350.0, inventory_kg=250.0)
    assert policy.last_diagnostics["inventory_regime"] == "excess"


def test_ignores_extra_kwargs_like_t_and_sigma():
    """Confirms this policy matches the shared quote_ask interface and safely
    ignores AS-specific kwargs like t/T/sigma passed uniformly by simulation.py."""
    policy = make_policy()
    ask = policy.quote_ask(mid_price=350.0, inventory_kg=150.0, t=0.5, T=1.0, sigma=0.35)
    assert ask == pytest.approx(350.0 * 1.04)
