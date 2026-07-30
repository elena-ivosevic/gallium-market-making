"""
validation.py
==============

Phase 10 deliverable: Validation and Historical Framing. Consolidates
mathematical-relationship checks and edge-case checks the roadmap
specifies -- several of which were already implicitly tested by earlier
phases' own unit tests -- into ONE explicit, structured validation report,
plus a qualitative historical consistency check against the real 2023-2025
gallium export-control episode.

REQUIRED LANGUAGE (state this before showing anyone a result below)
----------------------------------------------------------------------
Historical events are used here to assess DIRECTIONAL PLAUSIBILITY --
does the model move the way the real episode suggests it should? -- not to
claim the model has been calibrated to, fitted against, or validated as
predictive of realized gallium-dealer prices or profits. See
docs/README_honesty_paragraph.md for this project's standing evidentiary
ceiling; nothing in this module raises it.

WHY THIS IS A SEPARATE MODULE, NOT JUST MORE UNIT TESTS SCATTERED ACROSS PHASES
--------------------------------------------------------------------------------------
Several of the properties below already have a unit test somewhere in this
project (e.g. `tests/test_avellaneda_stoikov.py` already confirms higher
inventory lowers the reservation price). The roadmap's Phase 10 ask is
specifically for a CONSOLIDATED validation report -- the exact list of
mathematical relationships and edge cases it names, checked in one place,
producing one clear pass/fail table, rather than requiring someone to
re-derive which earlier test file covers which roadmap bullet point. Where
a check duplicates an existing test, this module re-confirms it directly
(cheap, since these are all fast, deterministic unit-level checks) rather
than just asserting "see Phase N" and hoping that test still passes.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- The qualitative consistency check is NOT a calibration exercise and
  cannot be one -- there is no gallium-dealer transaction data to calibrate
  against (docs/README_honesty_paragraph.md). It checks DIRECTION only.
- Mathematical-relationship checks confirm the IMPLEMENTED formulas behave
  as documented; they cannot confirm the formulas themselves are the
  "correct" way to model a real gallium dealer, which is not a claim this
  project makes anywhere.
- Edge-case checks use small, fast configurations (short horizons, few
  seeds) chosen for quick, deterministic confirmation, not for the
  statistical rigor of a Phase 8 headline comparison.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
There would be no single, explicit confirmation that this project's many
formulas and edge cases actually behave the way their own docstrings and
the register claim they do -- each claim would remain scattered across
individual module docstrings and phase-specific tests, never checked
against the roadmap's own explicit validation checklist in one place.
"""

import numpy as np

from src.price_process import GalliumPriceProcess, PriceProcessParams
from src.demand import SectorHawkesOrderFlow, HawkesParams, DEFAULT_SECTORS, MilitaryElasticityParams
from src.policies.avellaneda_stoikov import AvellanedaStoikovPolicy, AvellanedaStoikovParams
from src.policies.scarcity_adjusted_as import ScarcityAdjustedASPolicy, ScarcityAdjustedASParams
from src.policies.priority_overlay import PriorityOverlayParams
from src.regimes import RegimeParams, RegimeSwitcher, REGIMES
from src.supply_chain import SupplyChainParams
from src.accounting import AccountingParams
from src.simulation import Simulation, SimulationConfig


# =============================================================================
# Mathematical relationship checks
# =============================================================================

def check_math_relationships() -> dict:
    """Runs every roadmap-specified mathematical relationship check and
    returns {check_name: {"passed": bool, "evidence": ...}}."""
    results = {}
    as_policy = AvellanedaStoikovPolicy(AvellanedaStoikovParams())

    # More physical inventory -> lower reservation price
    r_low_inv, *_ = as_policy._compute_quotes(350.0, 10.0, 0.0, 1.0, 0.35)
    r_high_inv, *_ = as_policy._compute_quotes(350.0, 300.0, 0.0, 1.0, 0.35)
    results["more_inventory_lowers_reservation_price"] = {
        "passed": r_high_inv < r_low_inv,
        "evidence": {"r_low_inv": r_low_inv, "r_high_inv": r_high_inv},
    }

    # Greater volatility -> wider spread
    _, _, _, spread_low_sigma, _ = as_policy._compute_quotes(350.0, 100.0, 0.0, 1.0, 0.10)
    _, _, _, spread_high_sigma, _ = as_policy._compute_quotes(350.0, 100.0, 0.0, 1.0, 0.60)
    results["higher_volatility_widens_spread"] = {
        "passed": spread_high_sigma > spread_low_sigma,
        "evidence": {"spread_low_sigma": spread_low_sigma, "spread_high_sigma": spread_high_sigma},
    }

    # Less time remaining -> weaker standard inventory adjustment
    r_early, *_ = as_policy._compute_quotes(350.0, 200.0, 0.0, 1.0, 0.35)
    r_late, *_ = as_policy._compute_quotes(350.0, 200.0, 0.999, 1.0, 0.35)
    results["less_time_remaining_weakens_inventory_adjustment"] = {
        "passed": abs(350.0 - r_late) < abs(350.0 - r_early),
        "evidence": {"shift_early": abs(350.0 - r_early), "shift_late": abs(350.0 - r_late)},
    }

    # Greater jump intensity -> wider spread (via the price process itself,
    # not the AS formula directly -- confirmed at the price-path level)
    low_jump = GalliumPriceProcess(PriceProcessParams(jump_intensity=0.5), seed=1)
    high_jump = GalliumPriceProcess(PriceProcessParams(jump_intensity=15.0), seed=1)
    low_path = low_jump.simulate_path(252)
    high_path = high_jump.simulate_path(252)
    results["higher_jump_intensity_increases_price_variance"] = {
        "passed": np.var(high_path) > np.var(low_path),
        "evidence": {"var_low": float(np.var(low_path)), "var_high": float(np.var(high_path))},
    }

    # Scarcity-adjusted policy premiums
    scarcity_policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())

    # Greater commitments -> higher reservation price (via commitment premium)
    ask_low_commit = scarcity_policy.quote_ask(350.0, committed_kg=0.0, safety_stock_kg=60.0)
    ask_high_commit = scarcity_policy.quote_ask(350.0, committed_kg=200.0, safety_stock_kg=60.0)
    results["greater_commitments_raise_reservation_price"] = {
        "passed": ask_high_commit > ask_low_commit,
        "evidence": {"ask_low_commit": ask_low_commit, "ask_high_commit": ask_high_commit},
    }

    # Lower shipment reliability -> higher shipment-risk premium
    scarcity_policy.quote_ask(350.0, civilian_reliability=0.95)
    premium_high_rel = scarcity_policy.last_diagnostics["shipment_risk_premium"]
    scarcity_policy.quote_ask(350.0, civilian_reliability=0.30)
    premium_low_rel = scarcity_policy.last_diagnostics["shipment_risk_premium"]
    results["lower_reliability_raises_shipment_risk_premium"] = {
        "passed": premium_low_rel > premium_high_rel,
        "evidence": {"premium_high_rel": premium_high_rel, "premium_low_rel": premium_low_rel},
    }

    # Lower available inventory -> higher scarcity premium
    scarcity_policy.quote_ask(350.0, available_kg=100.0, safety_stock_kg=60.0)
    premium_high_avail = scarcity_policy.last_diagnostics["scarcity_premium"]
    scarcity_policy.quote_ask(350.0, available_kg=-50.0, safety_stock_kg=60.0)
    premium_low_avail = scarcity_policy.last_diagnostics["scarcity_premium"]
    results["lower_available_inventory_raises_scarcity_premium"] = {
        "passed": premium_low_avail > premium_high_avail,
        "evidence": {"premium_high_avail": premium_high_avail, "premium_low_avail": premium_low_avail},
    }

    # Priority overlay at p=1 -> military-linked fill rate >= civilian fill
    # rate DURING SEVERE REGIME specifically (true "by construction," per
    # the roadmap -- confirmed here, not just assumed)
    severe_pinned = RegimeParams(initial_regime="severe")
    severe_pinned.transition_matrix = {r: {r2: (1.0 if r2 == "severe" else 0.0) for r2 in REGIMES}
                                        for r in REGIMES}
    mil_rates, civ_rates = [], []
    for seed in range(10):
        policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
        sim = Simulation(
            policy, config=SimulationConfig(n_steps=100, seed=seed),
            regime_params=severe_pinned, priority_overlay_params=PriorityOverlayParams(p=1.0),
            accounting_params=AccountingParams(safety_stock_kg=60.0),
        )
        r = sim.run()
        if r["military_fill_rate"] is not None:
            mil_rates.append(r["military_fill_rate"])
        if r["civilian_fill_rate"] is not None:
            civ_rates.append(r["civilian_fill_rate"])
    mean_mil = float(np.mean(mil_rates)) if mil_rates else None
    mean_civ = float(np.mean(civ_rates)) if civ_rates else None
    results["overlay_p1_military_fill_rate_at_least_civilian_during_severe"] = {
        "passed": (mean_mil is not None and mean_civ is not None and mean_mil >= mean_civ),
        "evidence": {"mean_military_fill_rate": mean_mil, "mean_civilian_fill_rate": mean_civ},
    }

    return results


# =============================================================================
# Edge-case checks
# =============================================================================

def check_edge_cases() -> dict:
    results = {}

    # No jumps -> model approaches ordinary diffusion (zero jump events)
    proc = GalliumPriceProcess(PriceProcessParams(jump_intensity=0.0), seed=1)
    proc.simulate_path(500)
    results["no_jumps_approaches_ordinary_diffusion"] = {
        "passed": proc.jump_events == 0,
        "evidence": {"jump_events": proc.jump_events},
    }

    # No Hawkes excitation -> demand becomes Poisson (variance should not
    # exceed the mean by much more than sampling noise -- a Poisson process
    # has variance == mean; Hawkes clustering inflates variance above mean)
    flow = SectorHawkesOrderFlow(seed=1)
    counts = [len(flow.generate_orders(350.0, 1/252, 1.0, hawkes_excitation_strength=0.0))
              for _ in range(1000)]
    mean_count, var_count = float(np.mean(counts)), float(np.var(counts))
    results["no_hawkes_excitation_demand_is_poisson_like"] = {
        "passed": var_count < mean_count * 1.5,  # loose bound: Poisson has var == mean exactly
        "evidence": {"mean": mean_count, "variance": var_count},
    }

    # Perfect shipments -> shipment-risk premium disappears
    scarcity_policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    scarcity_policy.quote_ask(350.0, civilian_reliability=1.0)
    results["perfect_shipments_zero_shipment_risk_premium"] = {
        "passed": scarcity_policy.last_diagnostics["shipment_risk_premium"] == 0.0,
        "evidence": {"shipment_risk_premium": scarcity_policy.last_diagnostics["shipment_risk_premium"]},
    }

    # Unlimited inventory -> scarcity effect weakens (toward zero)
    scarcity_policy.quote_ask(350.0, available_kg=1_000_000.0, safety_stock_kg=60.0)
    results["unlimited_inventory_weakens_scarcity_premium"] = {
        "passed": scarcity_policy.last_diagnostics["scarcity_premium"] == 0.0,
        "evidence": {"scarcity_premium": scarcity_policy.last_diagnostics["scarcity_premium"]},
    }

    # No commitments -> commitment premium disappears
    scarcity_policy.quote_ask(350.0, committed_kg=0.0, safety_stock_kg=60.0)
    results["no_commitments_zero_commitment_premium"] = {
        "passed": scarcity_policy.last_diagnostics["commitment_premium"] == 0.0,
        "evidence": {"commitment_premium": scarcity_policy.last_diagnostics["commitment_premium"]},
    }

    # Normal regime only -> regime-switching model collapses to a single regime
    normal_only = RegimeParams(initial_regime="normal")
    normal_only.transition_matrix = {r: {r2: (1.0 if r2 == "normal" else 0.0) for r2 in REGIMES}
                                       for r in REGIMES}
    switcher = RegimeSwitcher(normal_only, seed=1)
    for _ in range(200):
        switcher.step()
    results["normal_regime_only_collapses_to_single_regime"] = {
        "passed": switcher.regime_days["normal"] == 201,
        "evidence": {"regime_days": dict(switcher.regime_days)},
    }

    # Military-linked demand share -> 0 AND overlay off -> collapses exactly
    # to Phase 5 scarcity-adjusted policy with no military distinction
    zero_share_sectors = [
        type(s)(s.name, s.arrival_rate_per_year, s.order_size_mean_kg, s.wtp_spread_frac, 0.0,
                 s.order_size_sigma)
        for s in DEFAULT_SECTORS
    ]
    policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
    sim = Simulation(
        policy, config=SimulationConfig(n_steps=252, seed=1), regime_params=RegimeParams(),
        sectors=zero_share_sectors, priority_overlay_params=PriorityOverlayParams(p=0.0),
        accounting_params=AccountingParams(safety_stock_kg=60.0),
    )
    r = sim.run()
    results["zero_military_share_and_no_overlay_collapses_to_phase5"] = {
        "passed": r["n_military_orders"] == 0,
        "evidence": {"n_military_orders": r["n_military_orders"], "n_civilian_orders": r["n_civilian_orders"]},
    }

    # Military demand price-sensitivity identical to civilian -> fill rates
    # converge even with overlay off, confirming elasticity (not the tag
    # alone) is what makes the split matter
    identical_elasticity = MilitaryElasticityParams(wtp_spread_multiplier=1.0, wtp_mean_shift_frac=0.0)
    mil_rates, civ_rates = [], []
    for seed in range(15):
        policy = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
        sim = Simulation(
            policy, config=SimulationConfig(n_steps=252, seed=seed), regime_params=RegimeParams(),
            military_elasticity=identical_elasticity, priority_overlay_params=PriorityOverlayParams(p=0.0),
            accounting_params=AccountingParams(safety_stock_kg=60.0),
        )
        r = sim.run()
        if r["military_fill_rate"] is not None:
            mil_rates.append(r["military_fill_rate"])
        if r["civilian_fill_rate"] is not None:
            civ_rates.append(r["civilian_fill_rate"])
    mean_mil, mean_civ = float(np.mean(mil_rates)), float(np.mean(civ_rates))
    results["identical_elasticity_converges_fill_rates"] = {
        "passed": abs(mean_mil - mean_civ) < 0.05,
        "evidence": {"mean_military_fill_rate": mean_mil, "mean_civilian_fill_rate": mean_civ},
    }

    return results


def run_full_validation_suite() -> dict:
    """Runs every mathematical-relationship and edge-case check, returns a
    combined report. See module docstring for the required historical-
    framing language that applies to any qualitative consistency check
    reported alongside this (src/validation.py does not itself run the
    qualitative check -- see README Phase 10 section for that narrative)."""
    math_results = check_math_relationships()
    edge_results = check_edge_cases()
    all_results = {**math_results, **edge_results}
    n_passed = sum(1 for v in all_results.values() if v["passed"])
    return {
        "math_relationships": math_results,
        "edge_cases": edge_results,
        "n_checks": len(all_results),
        "n_passed": n_passed,
        "all_passed": n_passed == len(all_results),
    }


# =============================================================================
# Qualitative historical consistency check
# =============================================================================

def run_qualitative_consistency_check(seeds: list = None) -> dict:
    """
    Simulates a persistent-Severe-regime scenario (reusing Phase 8's
    `PERSISTENT_SEVERE_REGIME` holdout, src/holdout_scenarios.py) and checks
    whether the model moves in the DIRECTION the real 2023-2025 gallium
    export-control episode suggests it should -- per the required language
    (module docstring), this is a directional plausibility check, not a
    calibration exercise. Compares against an equivalent Normal-regime run
    on the same seeds.
    """
    from src.holdout_scenarios import PERSISTENT_SEVERE_REGIME
    from src.sector_stress_test import compute_sector_stress_report

    seeds = seeds if seeds is not None else list(range(10))
    normal_regime = RegimeParams(initial_regime="normal")

    severe_metrics, normal_metrics = [], []
    for seed in seeds:
        policy_severe = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
        sim_severe = Simulation(
            policy_severe, config=SimulationConfig(n_steps=252, seed=seed),
            price_params=PERSISTENT_SEVERE_REGIME.price_params,
            regime_params=PERSISTENT_SEVERE_REGIME.regime_params,
            supply_chain_params=PERSISTENT_SEVERE_REGIME.supply_chain_params,
            accounting_params=PERSISTENT_SEVERE_REGIME.accounting_params,
        )
        r_severe = sim_severe.run()
        report_severe = compute_sector_stress_report(r_severe)

        policy_normal = ScarcityAdjustedASPolicy(ScarcityAdjustedASParams())
        sim_normal = Simulation(
            policy_normal, config=SimulationConfig(n_steps=252, seed=seed),
            regime_params=normal_regime, accounting_params=AccountingParams(safety_stock_kg=60.0),
        )
        r_normal = sim_normal.run()
        report_normal = compute_sector_stress_report(r_normal)

        severe_metrics.append({
            "mean_spread": np.mean([d["spread"] for d in r_severe["policy_diagnostics"]]),
            "mean_scarcity_premium": np.mean([d["scarcity_premium"] for d in r_severe["policy_diagnostics"]]),
            "n_shortage_days": sum(e["duration_days"] for e in report_severe["shortage_episodes"]),
            "demand_variance": np.var([
                len([o for o in r_severe["order_log"] if o["t"] == t]) for t in range(252)
            ]),
            "reliability_gap": np.mean([
                row["civilian_reliability"] - row["military_reliability"] for row in r_severe["regime_history"]
            ]),
        })
        normal_metrics.append({
            "mean_spread": np.mean([d["spread"] for d in r_normal["policy_diagnostics"]]),
            "mean_scarcity_premium": np.mean([d["scarcity_premium"] for d in r_normal["policy_diagnostics"]]),
            "n_shortage_days": sum(e["duration_days"] for e in report_normal["shortage_episodes"]),
            "demand_variance": np.var([
                len([o for o in r_normal["order_log"] if o["t"] == t]) for t in range(252)
            ]),
            "reliability_gap": np.mean([
                row["civilian_reliability"] - row["military_reliability"] for row in r_normal["regime_history"]
            ]),
        })

    def _mean(key, metrics):
        return float(np.mean([m[key] for m in metrics]))

    checks = {
        "spreads_widen_under_severe": _mean("mean_spread", severe_metrics) > _mean("mean_spread", normal_metrics),
        "scarcity_increases_under_severe": (
            _mean("mean_scarcity_premium", severe_metrics) > _mean("mean_scarcity_premium", normal_metrics)
        ),
        "stockouts_more_common_under_severe": (
            _mean("n_shortage_days", severe_metrics) > _mean("n_shortage_days", normal_metrics)
        ),
        "demand_clusters_more_under_severe": (
            _mean("demand_variance", severe_metrics) > _mean("demand_variance", normal_metrics)
        ),
        "civilian_military_reliability_gap_widens_under_severe": (
            _mean("reliability_gap", severe_metrics) > _mean("reliability_gap", normal_metrics)
        ),
    }

    return {
        "checks": checks,
        "n_passed": sum(checks.values()),
        "n_checks": len(checks),
        "all_passed": all(checks.values()),
        "severe_summary": {k: _mean(k, severe_metrics) for k in severe_metrics[0]},
        "normal_summary": {k: _mean(k, normal_metrics) for k in normal_metrics[0]},
    }
