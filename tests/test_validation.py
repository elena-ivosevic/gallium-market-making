import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from src.validation import (
    check_math_relationships, check_edge_cases, run_full_validation_suite,
    run_qualitative_consistency_check,
)


# ---- math relationship checks -----------------------------------------------

def test_all_math_relationship_checks_pass():
    results = check_math_relationships()
    failed = [name for name, r in results.items() if not r["passed"]]
    assert not failed, f"Failed math-relationship checks: {failed}"


def test_math_relationships_cover_every_roadmap_bullet():
    results = check_math_relationships()
    expected = {
        "more_inventory_lowers_reservation_price",
        "higher_volatility_widens_spread",
        "less_time_remaining_weakens_inventory_adjustment",
        "higher_jump_intensity_increases_price_variance",
        "greater_commitments_raise_reservation_price",
        "lower_reliability_raises_shipment_risk_premium",
        "lower_available_inventory_raises_scarcity_premium",
        "overlay_p1_military_fill_rate_at_least_civilian_during_severe",
    }
    assert set(results.keys()) == expected


def test_overlay_severe_regime_check_shows_a_real_gap():
    """The roadmap flags this relationship as 'true by construction' but
    still asks it to be confirmed in simulation -- and at a pinned Severe
    regime specifically, the gap should be large, not marginal (contrast
    with Phase 5/7's finding that the overlay's effect is small at DEFAULT,
    non-pinned calibration)."""
    results = check_math_relationships()
    evidence = results["overlay_p1_military_fill_rate_at_least_civilian_during_severe"]["evidence"]
    assert evidence["mean_military_fill_rate"] > evidence["mean_civilian_fill_rate"] + 0.05


# ---- edge case checks --------------------------------------------------------

def test_all_edge_case_checks_pass():
    results = check_edge_cases()
    failed = [name for name, r in results.items() if not r["passed"]]
    assert not failed, f"Failed edge-case checks: {failed}"


def test_edge_cases_cover_every_roadmap_bullet():
    results = check_edge_cases()
    expected = {
        "no_jumps_approaches_ordinary_diffusion",
        "no_hawkes_excitation_demand_is_poisson_like",
        "perfect_shipments_zero_shipment_risk_premium",
        "unlimited_inventory_weakens_scarcity_premium",
        "no_commitments_zero_commitment_premium",
        "normal_regime_only_collapses_to_single_regime",
        "zero_military_share_and_no_overlay_collapses_to_phase5",
        "identical_elasticity_converges_fill_rates",
    }
    assert set(results.keys()) == expected


def test_zero_military_share_edge_case_has_zero_military_orders_not_just_low():
    results = check_edge_cases()
    evidence = results["zero_military_share_and_no_overlay_collapses_to_phase5"]["evidence"]
    assert evidence["n_military_orders"] == 0
    assert evidence["n_civilian_orders"] > 0  # sanity: orders still happened at all


# ---- full suite ---------------------------------------------------------------

def test_run_full_validation_suite_aggregates_both_categories():
    report = run_full_validation_suite()
    assert report["n_checks"] == 16
    assert report["all_passed"] is True
    assert report["n_passed"] == 16


def test_full_validation_suite_runs_quickly():
    """A validation suite that takes minutes to run defeats its own purpose
    as a quick, re-runnable confirmation -- should complete in well under 10s."""
    import time
    t0 = time.time()
    run_full_validation_suite()
    assert time.time() - t0 < 10.0


# ---- qualitative consistency check -------------------------------------------

def test_qualitative_consistency_check_runs_and_returns_five_checks():
    report = run_qualitative_consistency_check(seeds=[1, 2, 3])
    assert report["n_checks"] == 5
    assert set(report["checks"].keys()) == {
        "spreads_widen_under_severe", "scarcity_increases_under_severe",
        "stockouts_more_common_under_severe", "demand_clusters_more_under_severe",
        "civilian_military_reliability_gap_widens_under_severe",
    }


def test_qualitative_check_civilian_military_gap_widens_under_severe():
    """This specific check should hold robustly -- the register's own
    Section 11.2 design guarantees Severe has a wider civilian/military
    reliability gap than Normal by construction."""
    report = run_qualitative_consistency_check(seeds=[1, 2, 3])
    assert report["checks"]["civilian_military_reliability_gap_widens_under_severe"] is True


def test_qualitative_check_spreads_widen_under_severe_holds():
    report = run_qualitative_consistency_check(seeds=[1, 2, 3])
    assert report["checks"]["spreads_widen_under_severe"] is True


def test_qualitative_check_documents_the_pricing_rationing_finding():
    """
    Confirms, directly, the mechanism behind the two checks that do NOT
    hold in the naively-expected direction (scarcity/stockouts don't
    increase under Severe): the scarcity-adjusted policy's own aggressive
    pricing under Severe rations demand so effectively that physical
    inventory is LESS depleted than under Normal, not more. This is a
    real, economically coherent finding (price rationing preventing
    shortages), not a bug -- confirmed here by checking fill rate is
    dramatically lower under Severe, which is the actual cause.
    """
    from src.policies.scarcity_adjusted_as import ScarcityAdjustedASPolicy, ScarcityAdjustedASParams
    from src.simulation import Simulation, SimulationConfig
    from src.regimes import RegimeParams
    from src.accounting import AccountingParams
    from src.holdout_scenarios import PERSISTENT_SEVERE_REGIME

    policy_severe = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    sim_severe = Simulation(
        policy_severe, config=SimulationConfig(n_steps=252, seed=1),
        price_params=PERSISTENT_SEVERE_REGIME.price_params,
        regime_params=PERSISTENT_SEVERE_REGIME.regime_params,
        supply_chain_params=PERSISTENT_SEVERE_REGIME.supply_chain_params,
        accounting_params=PERSISTENT_SEVERE_REGIME.accounting_params,
    )
    r_severe = sim_severe.run()

    policy_normal = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    sim_normal = Simulation(
        policy_normal, config=SimulationConfig(n_steps=252, seed=1),
        regime_params=RegimeParams(initial_regime="normal"),
        accounting_params=AccountingParams(safety_stock_kg=60.0),
    )
    r_normal = sim_normal.run()

    fill_rate_severe = r_severe["n_filled"] / r_severe["n_orders"]
    fill_rate_normal = r_normal["n_filled"] / r_normal["n_orders"]
    assert fill_rate_severe < fill_rate_normal * 0.5  # dramatically lower, not marginally
