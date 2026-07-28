import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.policies.dp_toy_example import (
    solve_toy_problem, HAND_DERIVED_V0, HAND_DERIVED_V1,
    HAND_DERIVED_V0_ACTIONS, HAND_DERIVED_V1_ACTIONS, STATES,
)


def test_programmatic_solver_matches_hand_derived_v1_exactly():
    result = solve_toy_problem()
    for s in STATES:
        assert result["V"][1][s] == pytest.approx(HAND_DERIVED_V1[s], abs=1e-9)


def test_programmatic_solver_matches_hand_derived_v0_exactly():
    result = solve_toy_problem()
    for s in STATES:
        assert result["V"][0][s] == pytest.approx(HAND_DERIVED_V0[s], abs=1e-9)


def test_programmatic_solver_matches_hand_derived_optimal_actions():
    result = solve_toy_problem()
    assert result["policy"][1] == HAND_DERIVED_V1_ACTIONS
    assert result["policy"][0] == HAND_DERIVED_V0_ACTIONS


def test_hold_is_optimal_at_high_inventory_despite_lower_immediate_reward():
    """The whole point of the toy example: Sell earns strictly more
    immediate reward than Hold in every state, but Hold wins at High
    because of the large terminal value -- confirming genuinely non-myopic
    (not just greedy) behavior."""
    from src.policies.dp_toy_example import REWARD

    result = solve_toy_problem()
    assert result["policy"][0]["high"] == "hold"
    assert result["policy"][1]["high"] == "hold"
    # And confirm Sell really does have the higher immediate reward at High,
    # so this isn't winning by having a better immediate payoff too.
    assert REWARD[("high", "sell")] > REWARD[("high", "hold")]


def test_sell_is_optimal_at_low_and_medium_inventory():
    result = solve_toy_problem()
    for t in (0, 1):
        assert result["policy"][t]["low"] == "sell"
        assert result["policy"][t]["medium"] == "sell"


def test_value_function_is_monotonically_increasing_in_inventory():
    """More inventory should never be worth less, at any decision point --
    a basic sanity property of a correctly-solved value function here."""
    result = solve_toy_problem()
    for t in (0, 1):
        assert result["V"][t]["low"] <= result["V"][t]["medium"] <= result["V"][t]["high"]
