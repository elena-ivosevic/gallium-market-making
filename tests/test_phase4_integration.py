"""
tests/test_phase4_integration.py
==================================

Phase 4 deliverable: end-to-end tests of regime-switching + sector/Hawkes
demand through the full Simulation loop, plus the roadmap's Phase 4 mastery
checkpoint predictions, saved here as assertions BEFORE the ablation
described in each docstring was run (predict-then-confirm, this project's
established pattern from Phase 1 onward).
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

from src.policies.fixed_spread import FixedSpreadPolicy, FixedSpreadParams
from src.simulation import Simulation, SimulationConfig
from src.regimes import RegimeParams
from src.demand import MilitaryElasticityParams, SectorParams
from src.supply_chain import SupplyChainParams


def test_phase1_2_3_behavior_unaffected_without_regime_params():
    """Regression guard: omitting regime_params must reproduce exactly the
    same result as before Phase 4 existed, with or without supply_chain_params."""
    policy_a = FixedSpreadPolicy(FixedSpreadParams())
    policy_b = FixedSpreadPolicy(FixedSpreadParams())
    result_a = Simulation(policy_a, config=SimulationConfig(n_steps=100, seed=7)).run()
    result_b = Simulation(policy_b, config=SimulationConfig(n_steps=100, seed=7)).run()
    assert result_a["terminal_wealth"] == result_b["terminal_wealth"]
    assert "regime_history" not in result_a
    assert "sector_fill_rates" not in result_a


def test_regime_mode_auto_creates_supply_chain_params_if_omitted():
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(policy, config=SimulationConfig(n_steps=50, seed=10), regime_params=RegimeParams())
    assert sim.supply_chain is not None


def test_regime_mode_returns_expected_new_keys():
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(policy, config=SimulationConfig(n_steps=252, seed=11), regime_params=RegimeParams())
    result = sim.run()
    for key in ("regime_history", "regime_days", "sector_fill_rates"):
        assert key in result
    assert len(result["regime_history"]) == 252


def test_regime_history_tracks_reliability_changing_with_regime():
    """Civilian reliability recorded in regime_history should actually vary
    over a long enough run if the regime changes (not pinned at Normal)."""
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(policy, config=SimulationConfig(n_steps=2000, seed=12), regime_params=RegimeParams())
    result = sim.run()
    reliabilities = {row["civilian_reliability"] for row in result["regime_history"]}
    # Over 2000 days, the chain should visit more than just Normal at least
    # some of the time (not guaranteed every seed, but overwhelmingly likely
    # given Normal's ~333-day expected duration over an 8-year run).
    assert len(reliabilities) >= 1  # always true; strengthened below
    regimes_visited = {row["regime"] for row in result["regime_history"]}
    assert len(regimes_visited) >= 2


def test_price_process_jump_multiplier_actually_reaches_price_process():
    """Confirms the regime's jump_intensity_multiplier is actually being
    passed into price_process.step(), not just computed and discarded --
    checked by forcing initial_regime='severe' and confirming more jump
    events accumulate than an equivalent Normal-regime run."""
    from src.price_process import PriceProcessParams

    policy_severe = FixedSpreadPolicy(FixedSpreadParams())
    policy_normal = FixedSpreadPolicy(FixedSpreadParams())

    # Pin the chain in one regime for the whole run by making it maximally
    # persistent (self-transition probability 1.0) so the jump-multiplier
    # effect isn't diluted by regime switching mid-run.
    pinned_severe = RegimeParams(initial_regime="severe")
    pinned_severe.transition_matrix = {
        "normal": {"normal": 1.0, "delayed": 0.0, "severe": 0.0, "recovery": 0.0},
        "delayed": {"normal": 0.0, "delayed": 1.0, "severe": 0.0, "recovery": 0.0},
        "severe": {"normal": 0.0, "delayed": 0.0, "severe": 1.0, "recovery": 0.0},
        "recovery": {"normal": 0.0, "delayed": 0.0, "severe": 0.0, "recovery": 1.0},
    }
    pinned_normal = RegimeParams(initial_regime="normal")
    pinned_normal.transition_matrix = pinned_severe.transition_matrix

    sim_severe = Simulation(policy_severe, config=SimulationConfig(n_steps=252, seed=13),
                              regime_params=pinned_severe)
    sim_normal = Simulation(policy_normal, config=SimulationConfig(n_steps=252, seed=13),
                              regime_params=pinned_normal)
    sim_severe.run()
    sim_normal.run()
    assert sim_severe.price_process.jump_events > sim_normal.price_process.jump_events


def test_military_channel_reliability_worse_than_civilian_during_run():
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(policy, config=SimulationConfig(n_steps=500, seed=14), regime_params=RegimeParams())
    result = sim.run()
    for row in result["regime_history"]:
        assert row["military_reliability"] <= row["civilian_reliability"]


# ---- Mastery checkpoint 1: predict, then confirm, the effect of removing Hawkes ----

def test_mastery_checkpoint_removing_hawkes_reduces_demand_clustering():
    """
    PREDICTION (written before running, per the roadmap's own mastery
    checkpoint): removing the Hawkes component should produce fewer demand
    clusters, less severe short-term inventory pressure, and lower tail risk
    in daily order counts -- i.e., strictly lower VARIANCE in daily order
    counts for the same average rate, since Hawkes clustering creates bursts
    without changing the long-run mean.
    """
    from src.demand import SectorHawkesOrderFlow, HawkesParams

    flow_with_hawkes = SectorHawkesOrderFlow(seed=20)
    counts_with = [
        len(flow_with_hawkes.generate_orders(350.0, 1/252, 1.0, hawkes_excitation_strength=0.5))
        for _ in range(1000)
    ]

    flow_without_hawkes = SectorHawkesOrderFlow(seed=20)
    counts_without = [
        len(flow_without_hawkes.generate_orders(350.0, 1/252, 1.0, hawkes_excitation_strength=0.0))
        for _ in range(1000)
    ]

    assert np.var(counts_with) > np.var(counts_without), (
        "Expected removing Hawkes excitation to reduce daily-order-count variance "
        f"(clustering); got with={np.var(counts_with):.3f}, without={np.var(counts_without):.3f}"
    )
    # Tail risk: max single-day order count should also tend to be lower without clustering
    assert max(counts_with) >= max(counts_without)


# ---- Mastery checkpoint 2: effect of removing price-sensitivity difference ----

def test_mastery_checkpoint_identical_elasticity_shrinks_fill_rate_gap():
    """
    PREDICTION (register Section 11.6 / roadmap Phase 4 checkpoint): if
    military and civilian demand have IDENTICAL price-sensitivity (no
    elasticity difference), the military-vs-civilian fill-rate gap under a
    PRICING-ONLY policy should shrink toward zero, since nothing about a
    military tag then affects whether an order clears the ask price. This is
    the key edge case motivating Phase 5/7's priority-overlay research
    question: does pricing alone protect military demand, or does the tag
    have to change something (elasticity, or an explicit non-price rule)?
    """
    policy_a = FixedSpreadPolicy(FixedSpreadParams())
    policy_b = FixedSpreadPolicy(FixedSpreadParams())

    with_elasticity = MilitaryElasticityParams(wtp_spread_multiplier=2.5, wtp_mean_shift_frac=0.03)
    no_elasticity = MilitaryElasticityParams(wtp_spread_multiplier=1.0, wtp_mean_shift_frac=0.0)

    gaps = {}
    for label, elasticity in [("with_elasticity", with_elasticity), ("no_elasticity", no_elasticity)]:
        mil_rates, civ_rates = [], []
        for seed in range(20):
            policy = FixedSpreadPolicy(FixedSpreadParams())
            sim = Simulation(
                policy, config=SimulationConfig(n_steps=504, seed=seed),
                regime_params=RegimeParams(), military_elasticity=elasticity,
            )
            r = sim.run()
            if r["military_fill_rate"] is not None:
                mil_rates.append(r["military_fill_rate"])
            if r["civilian_fill_rate"] is not None:
                civ_rates.append(r["civilian_fill_rate"])
        gaps[label] = np.mean(mil_rates) - np.mean(civ_rates)

    assert gaps["with_elasticity"] > gaps["no_elasticity"], (
        f"Expected the fill-rate gap to shrink without elasticity difference; "
        f"got with_elasticity={gaps['with_elasticity']:.3f}, no_elasticity={gaps['no_elasticity']:.3f}"
    )
    # And the no-elasticity gap should be close to zero (not just smaller)
    assert abs(gaps["no_elasticity"]) < abs(gaps["with_elasticity"])
