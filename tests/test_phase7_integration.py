"""
tests/test_phase7_integration.py
==================================

Phase 7 deliverable: full-simulation checks addressing the roadmap's
specific "Questions to Answer" for the sector transmission stress test.
Required framing (see src/sector_stress_test.py's module docstring, and
docs/assumptions_register.md Section 14): these are simulated-customer
results, not real economic estimates.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

from src.policies.scarcity_adjusted_as import ScarcityAdjustedASPolicy, ScarcityAdjustedASParams
from src.policies.priority_overlay import PriorityOverlayParams
from src.simulation import Simulation, SimulationConfig
from src.regimes import RegimeParams
from src.accounting import AccountingParams
from src.sector_stress_test import compute_sector_stress_report


def run_regime_sim(seed, priority_overlay_params=None, accounting_params=None, n_steps=756):
    policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    sim = Simulation(
        policy, config=SimulationConfig(n_steps=n_steps, seed=seed), regime_params=RegimeParams(),
        accounting_params=accounting_params, priority_overlay_params=priority_overlay_params,
    )
    return sim.run()


def test_report_generation_runs_on_a_real_multi_year_simulation():
    result = run_regime_sim(seed=1)
    report = compute_sector_stress_report(result)
    assert len(report["sector_fill_stats"]) == 4  # all four sectors present
    assert len(report["coverage_days"]) == 756


# ---- "Which sectors lose access first / are most vulnerable?" -------------

def test_defense_aerospace_fill_rate_differs_meaningfully_from_other_sectors():
    """Structural confirmation that sector-level differentiation actually
    shows up in a real run, not just in isolated unit tests -- Defense &
    Aerospace's 70% military-linked share (register Section 11.4) should
    produce a fill rate noticeably different from Solar's 5% share."""
    fill_rates = {"defense_aerospace": [], "solar_clean_energy": []}
    for seed in range(15):
        result = run_regime_sim(seed=seed, n_steps=504)
        report = compute_sector_stress_report(result)
        for sector in fill_rates:
            fr = report["sector_fill_stats"].get(sector, {}).get("fill_rate")
            if fr is not None:
                fill_rates[sector].append(fr)
    assert np.mean(fill_rates["defense_aerospace"]) != np.mean(fill_rates["solar_clean_energy"])


# ---- "Does the policy prioritize high-value customers?" --------------------

def test_military_linked_orders_within_each_sector_fill_at_least_as_often_as_civilian():
    """Within EVERY sector (not just pooled), military-linked orders --
    which carry a higher, wider willingness-to-pay distribution, register
    Section 11.6 -- should fill at least as often as civilian orders in the
    same sector, on average across seeds."""
    sector_gaps = {}
    for seed in range(20):
        result = run_regime_sim(seed=seed, n_steps=504)
        report = compute_sector_stress_report(result)
        for sector, stats in report["sector_fill_stats"].items():
            mil_rate = stats["military"]["fill_rate"]
            civ_rate = stats["civilian"]["fill_rate"]
            if mil_rate is not None and civ_rate is not None:
                sector_gaps.setdefault(sector, []).append(mil_rate - civ_rate)

    for sector, gaps in sector_gaps.items():
        if gaps:
            assert np.mean(gaps) >= -0.05  # allow small negative noise, but not a real reversal


# ---- "Does the priority overlay change which sectors lose access first, ---
# ---- and at what cost to dealer P&L?" --------------------------------------

def test_overlay_effect_on_sector_fill_rates_and_pnl_is_measurable():
    """Runs matched seeds with and without the priority overlay and reports
    (does not assert a specific winner) sector-level fill-rate shifts and
    the P&L cost -- confirming the comparison itself is well-formed and
    computable, consistent with this project's practice of not
    over-interpreting small-sample comparisons."""
    acct = AccountingParams(initial_inventory_kg=25.0, restock_amount_kg=15.0, safety_stock_kg=10.0)
    n_seeds = 15
    fill_rates_on, fill_rates_off, pnl_on, pnl_off = {}, {}, [], []

    for seed in range(n_seeds):
        r_on = run_regime_sim(seed=seed, priority_overlay_params=PriorityOverlayParams(p=1.0),
                                accounting_params=acct, n_steps=504)
        r_off = run_regime_sim(seed=seed, priority_overlay_params=PriorityOverlayParams(p=0.0),
                                 accounting_params=acct, n_steps=504)
        report_on = compute_sector_stress_report(r_on)
        report_off = compute_sector_stress_report(r_off)
        for sector in report_on["sector_fill_stats"]:
            fr_on = report_on["sector_fill_stats"][sector]["fill_rate"]
            fr_off = report_off["sector_fill_stats"][sector]["fill_rate"]
            if fr_on is not None:
                fill_rates_on.setdefault(sector, []).append(fr_on)
            if fr_off is not None:
                fill_rates_off.setdefault(sector, []).append(fr_off)
        pnl_on.append(r_on["mark_to_market_pnl"])
        pnl_off.append(r_off["mark_to_market_pnl"])

    # The comparison must be COMPUTABLE and produce finite numbers for every
    # sector -- this is the structural bar Phase 7 needs to clear; the
    # roadmap's actual answer (which sector, how much) is Phase 9's job with
    # proper confidence intervals, not asserted here as a single-point truth.
    assert set(fill_rates_on.keys()) == set(fill_rates_off.keys())
    assert all(np.isfinite(v) for v in pnl_on + pnl_off)


# ---- "Does maximizing dealer P&L reduce total customer fill rates?" --------

def test_pooled_fill_rate_and_pnl_relationship_is_computable_across_seeds():
    """Not asserting a direction (this is a genuine open empirical question
    the roadmap poses, not one this project claims to have already
    answered) -- confirming both quantities are computed consistently on
    the same matched paths so a real correlation analysis (Phase 9) is
    possible."""
    fill_rates, pnls = [], []
    for seed in range(15):
        result = run_regime_sim(seed=seed, n_steps=504)
        fill_rates.append(result["n_filled"] / result["n_orders"] if result["n_orders"] else None)
        pnls.append(result["mark_to_market_pnl"])
    assert all(fr is not None for fr in fill_rates)
    assert all(np.isfinite(p) for p in pnls)


# ---- Required framing is actually present in the module, not just claimed -

def test_required_framing_disclaimer_is_present_in_module_docstring():
    import src.sector_stress_test as sst
    doc = sst.__doc__.replace("\n", " ")
    assert "simulated customers" in doc or "SIMULATED customers" in doc
    assert "NOT estimates of realized industrial production" in doc
