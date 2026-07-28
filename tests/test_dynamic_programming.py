import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.policies.dynamic_programming import (
    DynamicProgrammingPolicy, DynamicProgrammingParams, ACTIONS, ACTION_MARKUPS,
)
from src.regimes import REGIMES


def make_policy(n_steps=100, safety_stock_kg=60.0, **overrides):
    params = DynamicProgrammingParams(**overrides) if overrides else DynamicProgrammingParams()
    return DynamicProgrammingPolicy(params, n_steps=n_steps, safety_stock_kg=safety_stock_kg)


def test_solves_without_error_and_produces_full_tables():
    policy = make_policy(n_steps=50)
    assert len(policy.policy_table) == 50
    assert len(policy.value_table) == 51  # includes terminal
    for regime in REGIMES:
        assert regime in policy.policy_table[0]
        assert len(policy.policy_table[0][regime]) == policy.p.n_inventory_bins


def test_every_policy_table_entry_is_a_valid_action():
    policy = make_policy(n_steps=30)
    for day in range(30):
        for regime in REGIMES:
            for b in range(policy.p.n_inventory_bins):
                assert policy.policy_table[day][regime][b] in ACTIONS


def test_value_table_has_no_nan_or_inf():
    policy = make_policy(n_steps=30)
    for day in range(31):
        for regime in REGIMES:
            for b in range(policy.p.n_inventory_bins):
                v = policy.value_table[day][regime][b]
                assert np.isfinite(v)


def test_inventory_to_bin_respects_configured_edges():
    policy = make_policy(safety_stock_kg=60.0)
    # edges: [0, 30, 60, 120, 240, inf]
    assert policy._inventory_to_bin(0.0) == 0
    assert policy._inventory_to_bin(29.0) == 0
    assert policy._inventory_to_bin(30.0) == 1
    assert policy._inventory_to_bin(60.0) == 2
    assert policy._inventory_to_bin(120.0) == 3
    assert policy._inventory_to_bin(500.0) == 4


def test_fill_probability_decreases_with_markup():
    policy = make_policy()
    assert policy._fill_probability(0.01) > policy._fill_probability(0.04)
    assert policy._fill_probability(0.04) > policy._fill_probability(0.10)
    assert policy._fill_probability(1.00) < 0.01  # stop markup: near-zero fill chance


def test_quote_ask_uses_action_specific_markup():
    policy = make_policy(n_steps=100)
    ask = policy.quote_ask(mid_price=350.0, inventory_kg=1000.0, t=0.0, T=1.0, regime_name="normal")
    action = policy.last_diagnostics["action"]
    expected = 350.0 * (1.0 + ACTION_MARKUPS[action])
    assert ask == pytest.approx(expected)


def test_quote_ask_degrades_gracefully_without_regime_name():
    """Outside regime mode (regime_name=None), the policy should default to
    'normal' regime rather than erroring."""
    policy = make_policy(n_steps=100)
    ask = policy.quote_ask(mid_price=350.0, inventory_kg=100.0, t=0.0, T=1.0)
    assert ask > 0
    assert policy.last_diagnostics["regime"] == "normal"


def test_wants_emergency_purchase_reflects_last_action():
    policy = make_policy(n_steps=100, safety_stock_kg=60.0)
    # Query at a very low inventory, early in the horizon -- expect emergency_purchase
    policy.quote_ask(mid_price=350.0, inventory_kg=0.0, t=0.0, T=1.0, regime_name="normal")
    wants_emergency = policy.wants_emergency_purchase()
    assert wants_emergency == (policy.last_diagnostics["action"] == "emergency_purchase")


def test_low_inventory_more_likely_to_select_emergency_purchase_than_high_inventory():
    """A core, directly testable qualitative property: the DP should be at
    least as inclined toward emergency_purchase at low inventory as at high
    inventory, early in the horizon (when there's time to benefit from it)."""
    policy = make_policy(n_steps=252, safety_stock_kg=60.0)
    low_bin_action = policy.policy_table[0]["normal"][0]
    high_bin_action = policy.policy_table[0]["normal"][4]
    # At minimum, the highest bin should never choose emergency_purchase
    # when the lowest bin does not also -- i.e. emergency behavior is
    # monotonically (weakly) decreasing in inventory.
    if high_bin_action == "emergency_purchase":
        assert low_bin_action == "emergency_purchase"


def test_emergency_purchase_less_attractive_near_the_horizon():
    """Mastery-checkpoint-adjacent property: near the end of the horizon,
    there's less future benefit to restocking, so emergency_purchase should
    become less likely than early in the horizon, at the same low bin."""
    policy = make_policy(n_steps=252, safety_stock_kg=60.0)
    early_action = policy.policy_table[0]["normal"][0]
    late_action = policy.policy_table[251]["normal"][0]
    # Not asserting a specific action, but if emergency_purchase is chosen
    # anywhere, it should be more (or equally) common early than late.
    early_is_emergency = early_action == "emergency_purchase"
    late_is_emergency = late_action == "emergency_purchase"
    assert early_is_emergency or not late_is_emergency  # late=emergency implies early=emergency too


def test_restock_markup_frac_matches_normal_action_markup():
    policy = make_policy()
    assert policy.restock_markup_frac() == ACTION_MARKUPS["normal"]


def test_solve_time_is_fast_for_a_full_year_horizon():
    """Tractability sanity check -- backward induction over 252 days x 5
    bins x 4 regimes x 5 actions should solve in well under a second."""
    import time
    t0 = time.time()
    make_policy(n_steps=252)
    elapsed = time.time() - t0
    assert elapsed < 2.0
