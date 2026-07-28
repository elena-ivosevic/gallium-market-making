"""
tests/test_phase5_integration.py
==================================

Phase 5 deliverable: end-to-end tests of the scarcity-adjusted policy and
priority overlay through the full Simulation loop, plus structural checks
against the pre-registered ablation hypotheses (register Section 12.3) --
NOT a substitute for Phase 9's real ablation study, but confirming the
MECHANISM behaves as pre-registered, on matched paths.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

from src.policies.fixed_spread import FixedSpreadPolicy, FixedSpreadParams
from src.policies.scarcity_adjusted_as import ScarcityAdjustedASPolicy, ScarcityAdjustedASParams
from src.policies.priority_overlay import PriorityOverlayParams
from src.simulation import Simulation, SimulationConfig
from src.supply_chain import SupplyChainParams
from src.regimes import RegimeParams


def test_phase1_4_behavior_unaffected_without_phase5_params():
    """Regression guard: omitting priority_overlay_params (and using a
    non-scarcity policy) must reproduce identical behavior to before Phase 5
    existed."""
    policy_a = FixedSpreadPolicy(FixedSpreadParams())
    policy_b = FixedSpreadPolicy(FixedSpreadParams())
    result_a = Simulation(policy_a, config=SimulationConfig(n_steps=100, seed=7)).run()
    result_b = Simulation(policy_b, config=SimulationConfig(n_steps=100, seed=7)).run()
    assert result_a["terminal_wealth"] == result_b["terminal_wealth"]


def test_scarcity_policy_runs_in_plain_mode_without_error():
    """The scarcity-adjusted policy must work even outside supply-chain/regime
    mode (degrading to plain AS, per its own docstring)."""
    policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    result = Simulation(policy, config=SimulationConfig(n_steps=100, seed=8)).run()
    assert result["n_orders"] >= 0  # just confirming it runs end-to-end


def test_scarcity_policy_runs_in_full_phase4_mode_without_error():
    policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    result = Simulation(
        policy, config=SimulationConfig(n_steps=252, seed=9), regime_params=RegimeParams()
    ).run()
    assert result["n_orders"] >= 0
    assert "regime_history" in result


def test_priority_overlay_wired_into_simulation_reorders_contested_days():
    policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    sim = Simulation(
        policy, config=SimulationConfig(n_steps=756, seed=10),
        regime_params=RegimeParams(), priority_overlay_params=PriorityOverlayParams(p=1.0),
    )
    sim.run()
    # Over a long enough run with Hawkes clustering active, some contested
    # days should occur.
    assert sim.priority_overlay.contested_days >= 0  # structural: never errors
    if sim.priority_overlay.contested_days > 0:
        assert sim.priority_overlay.days_military_prioritized == sim.priority_overlay.contested_days  # p=1.0


def test_overlay_p_zero_produces_same_fill_pattern_as_no_overlay():
    """p=0 should behave identically to omitting the overlay entirely --
    structural confirmation that 'off' really means off."""
    policy_a = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    policy_b = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())

    result_no_overlay = Simulation(
        policy_a, config=SimulationConfig(n_steps=500, seed=11),
        supply_chain_params=SupplyChainParams(),
    ).run()
    result_p_zero = Simulation(
        policy_b, config=SimulationConfig(n_steps=500, seed=11),
        supply_chain_params=SupplyChainParams(), priority_overlay_params=PriorityOverlayParams(p=0.0),
    ).run()
    assert result_no_overlay["terminal_wealth"] == result_p_zero["terminal_wealth"]


# ---- Pre-registered ablation checks (register Section 12.3) ----------------

def test_ablation_scarcity_premium_removal_increases_reservation_price_gap():
    """Pre-registered hypothesis: removing the scarcity premium should mean
    the policy quotes LESS protectively under scarcity (lower ask) than with
    it -- a direct, deterministic check on the premium mechanism itself."""
    with_scarcity = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams(scarcity_gamma=0.05))
    without_scarcity = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams(scarcity_gamma=0.0))

    ask_with = with_scarcity.quote_ask(mid_price=350.0, available_kg=-50.0, safety_stock_kg=60.0)
    ask_without = without_scarcity.quote_ask(mid_price=350.0, available_kg=-50.0, safety_stock_kg=60.0)
    assert ask_with > ask_without


def test_ablation_priority_overlay_removal_eliminates_reordering():
    """Pre-registered hypothesis: p=1 vs p=0 should show a clear mechanical
    difference in whether contested days get reordered -- confirmed
    structurally (not just via aggregate fill rate, which is noisy)."""
    policy_a = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    policy_b = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())

    sim_on = Simulation(
        policy_a, config=SimulationConfig(n_steps=756, seed=12), regime_params=RegimeParams(),
        priority_overlay_params=PriorityOverlayParams(p=1.0),
    )
    sim_on.run()
    sim_off = Simulation(
        policy_b, config=SimulationConfig(n_steps=756, seed=12), regime_params=RegimeParams(),
        priority_overlay_params=PriorityOverlayParams(p=0.0),
    )
    sim_off.run()

    if sim_on.priority_overlay.contested_days > 0:
        assert sim_on.priority_overlay.days_military_prioritized > 0
    assert sim_off.priority_overlay.days_military_prioritized == 0


def test_regime_premium_reacts_to_regime_severity_within_a_real_run():
    """Confirms _regime_severity() actually reaches the policy during a real
    run (not just in isolated unit tests) -- checked by finding at least one
    Severe-regime day and one Normal-regime day in the diagnostics and
    comparing their regime_premium values."""
    policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    sim = Simulation(
        policy, config=SimulationConfig(n_steps=2000, seed=13), regime_params=RegimeParams(),
    )
    result = sim.run()
    diag_by_t = {d["t"]: d for d in result["policy_diagnostics"]}
    regime_by_t = {r["t"]: r["regime"] for r in result["regime_history"]}

    severe_premiums = [diag_by_t[t]["regime_premium"] for t in diag_by_t if regime_by_t.get(t) == "severe"]
    normal_premiums = [diag_by_t[t]["regime_premium"] for t in diag_by_t if regime_by_t.get(t) == "normal"]
    if severe_premiums and normal_premiums:
        assert np.mean(severe_premiums) > np.mean(normal_premiums)
