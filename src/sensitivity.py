"""
sensitivity.py
================

Phase 9 deliverable: Sensitivity Analysis and Tornado Chart.

WHAT THIS MODULE DOES
------------------------
For each of the roadmap's eleven named parameters (plus the priority
overlay's strictness `p`, which the roadmap calls out for its own
continuous sweep), this module runs the full model at a LOW and a HIGH
value, holding every other parameter at its registered default, and
measures the resulting swing in mean mark-to-market P&L across matched
seeds (src/evaluation.py). Sorting by swing magnitude produces tornado-
chart data: which single assumption moves the headline result the most.

WHY LOW/HIGH BOUNDS, NOT A FULL CONTINUOUS SWEEP, FOR MOST PARAMETERS
--------------------------------------------------------------------------
A tornado chart is specifically a LOW/HIGH-per-parameter visualization by
convention -- its entire point is a fast, at-a-glance ranking of which
assumptions matter most, not a full response curve for every parameter
(that would be eleven separate line charts). The priority overlay's `p` is
the one parameter the roadmap explicitly asks to sweep continuously
(0 to 1, not just endpoints) precisely because it is this project's other
central research lever (register Section 12.2) -- `sweep_overlay_strictness`
below does that separately from the tornado bounds.

WHY EACH PARAMETER'S LOW/HIGH BOUNDS ARE WHAT THEY ARE
------------------------------------------------------------
Logged in full in docs/assumptions_register.md, Section 16 -- in short,
each bound is either a previously-registered ALTERNATIVE value already used
elsewhere in this project (e.g. the holdout scenarios' reliability figures,
Phase 8) or a symmetric +/-50% perturbation of the registered default where
no other project-internal alternative already exists. No bound was chosen
by first running the sweep and picking whatever produced an interesting
result -- they are fixed before any sensitivity result is examined, the
same discipline as Phase 5's pre-registered ablation table.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Only ONE parameter is varied at a time; this is a one-at-a-time (OAT)
  sensitivity design, not a full factorial or Sobol-index variance
  decomposition -- it cannot detect INTERACTION effects between parameters
  (e.g., "safety stock only matters when reliability is also low").
- Seed counts here (10-20 per point, chosen for runtime) are smaller than
  Phase 8's headline comparisons (30-40) -- tornado-chart rankings should be
  read as indicative orderings, not each individually holding to a formal
  significance threshold. Confidence intervals are still computed and
  reported (never a bare number, per this project's own mastery checkpoint),
  but many will be wide at these seed counts.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
There would be no evidence for which of this project's many judgment-call
parameters (flagged "Sensitivity: High" throughout the register since Phase
0) actually deserve that flag versus which turn out not to matter much --
the register's own Section 1 rule ("do not let the sensitivity analysis
'discover' that a parameter matters if it was already flagged High here")
would have nothing to confirm or overturn those priors against.
"""

from src.price_process import PriceProcessParams
from src.regimes import RegimeParams
from src.supply_chain import SupplyChainParams
from src.accounting import AccountingParams
from src.demand import SectorParams, DEFAULT_SECTORS, HawkesParams
from src.policies.scarcity_adjusted_as import ScarcityAdjustedASPolicy, ScarcityAdjustedASParams
from src.policies.priority_overlay import PriorityOverlayParams
from src.simulation import Simulation, SimulationConfig
from src.evaluation import compute_run_metrics, confidence_interval


def _run_scenario(seeds, n_steps, price_params=None, regime_params=None,
                    supply_chain_params=None, accounting_params=None, sectors=None,
                    hawkes_params=None, policy_params=None, overlay_p=1.0) -> list:
    results = []
    for seed in seeds:
        policy = ScarcityAdjustedASPolicy(policy_params or ScarcityAdjustedASParams())
        sim = Simulation(
            policy, config=SimulationConfig(n_steps=n_steps, seed=seed),
            price_params=price_params, regime_params=regime_params or RegimeParams(),
            supply_chain_params=supply_chain_params,
            accounting_params=accounting_params or AccountingParams(safety_stock_kg=60.0),
            sectors=sectors, hawkes_params=hawkes_params,
            priority_overlay_params=PriorityOverlayParams(p=overlay_p),
        )
        results.append(sim.run())
    return results


def _pnl_ci(results):
    return confidence_interval([compute_run_metrics(r)["mark_to_market_pnl"] for r in results])


def _scaled_hawkes_excitation(mult):
    p = RegimeParams()
    p.hawkes_excitation = {k: v * mult for k, v in p.hawkes_excitation.items()}
    return p


def _scaled_sectors(mult):
    return [
        SectorParams(s.name, s.arrival_rate_per_year * mult, s.order_size_mean_kg,
                     s.wtp_spread_frac, s.military_linked_share, s.order_size_sigma)
        for s in DEFAULT_SECTORS
    ]


def _scaled_military_share(mult):
    return [
        SectorParams(s.name, s.arrival_rate_per_year, s.order_size_mean_kg,
                     s.wtp_spread_frac, min(1.0, s.military_linked_share * mult), s.order_size_sigma)
        for s in DEFAULT_SECTORS
    ]


def _scaled_reliability_regime_params(mult):
    """
    Scales EVERY regime's civilian/military reliability by `mult` (capped
    at 1.0). This exists because of a real architectural discovery made
    while building this module: in regime mode, `SupplyChainParams.reliability`
    /`.reliability_military` are OVERWRITTEN every single day by
    `RegimeSwitcher`'s own reliability dict (src/simulation.py's regime-mode
    loop) -- so passing a different `SupplyChainParams.reliability` while
    `regime_params` is also active (the default for every sensitivity run in
    this module) has ZERO effect. This was caught directly: an early version
    of the "shipment_reliability" tornado row showed an EXACT zero swing
    (identical P&L values, not just similar), which is what motivated
    checking rather than trusting a suspiciously clean number. Sweeping
    reliability meaningfully in regime mode requires scaling
    `RegimeParams.civilian_reliability`/`.military_reliability` instead, or
    alongside, `SupplyChainParams` -- done here.
    """
    p = RegimeParams()
    p.civilian_reliability = {k: min(1.0, v * mult) for k, v in p.civilian_reliability.items()}
    p.military_reliability = {k: min(1.0, v * mult) for k, v in p.military_reliability.items()}
    return p


# ---- the eleven named parameters, each as a (low_fn, high_fn) pair ---------

def build_tornado_specs() -> dict:
    """Returns {parameter_name: (low_kwargs_fn, high_kwargs_fn)}, each a
    zero-arg callable returning a dict of _run_scenario kwargs. Bounds are
    documented in docs/assumptions_register.md, Section 16."""
    return {
        "risk_aversion": (
            lambda: dict(policy_params=ScarcityAdjustedASParams(risk_aversion=3.5e-6 * 0.5)),
            lambda: dict(policy_params=ScarcityAdjustedASParams(risk_aversion=3.5e-6 * 1.5)),
        ),
        "jump_intensity": (
            lambda: dict(price_params=PriceProcessParams(jump_intensity=1.5)),
            lambda: dict(price_params=PriceProcessParams(jump_intensity=4.5)),
        ),
        "jump_size": (
            lambda: dict(price_params=PriceProcessParams(jump_up_scale=0.09, jump_down_scale=0.035)),
            lambda: dict(price_params=PriceProcessParams(jump_up_scale=0.27, jump_down_scale=0.105)),
        ),
        "shipment_reliability": (
            # See _scaled_reliability_regime_params' docstring for why this
            # scales RegimeParams, not SupplyChainParams, in regime mode.
            lambda: dict(regime_params=_scaled_reliability_regime_params(0.5),
                         supply_chain_params=SupplyChainParams(reliability=0.475, reliability_military=0.375)),
            lambda: dict(regime_params=_scaled_reliability_regime_params(1.0),
                         supply_chain_params=SupplyChainParams(reliability=0.95, reliability_military=0.75)),
        ),
        "shipment_lead_time": (
            lambda: dict(supply_chain_params=SupplyChainParams(lead_time_days=7)),
            lambda: dict(supply_chain_params=SupplyChainParams(lead_time_days=28)),
        ),
        "safety_stock": (
            lambda: dict(accounting_params=AccountingParams(safety_stock_kg=30.0)),
            lambda: dict(accounting_params=AccountingParams(safety_stock_kg=120.0)),
        ),
        "hawkes_excitation": (
            lambda: dict(regime_params=_scaled_hawkes_excitation(0.5)),
            lambda: dict(regime_params=_scaled_hawkes_excitation(1.5)),
        ),
        "hawkes_decay": (
            lambda: dict(hawkes_params=HawkesParams(decay_rate_per_year=16.0)),  # faster decay, shorter memory
            lambda: dict(hawkes_params=HawkesParams(decay_rate_per_year=4.0)),   # slower decay, longer memory
        ),
        "sector_demand": (
            lambda: dict(sectors=_scaled_sectors(0.5)),
            lambda: dict(sectors=_scaled_sectors(1.5)),
        ),
        "replacement_cost_curvature": (
            lambda: dict(supply_chain_params=SupplyChainParams(replacement_cost_curvature=1.0)),
            lambda: dict(supply_chain_params=SupplyChainParams(replacement_cost_curvature=3.0)),
        ),
        "military_linked_demand_share": (
            lambda: dict(sectors=_scaled_military_share(0.5)),
            lambda: dict(sectors=_scaled_military_share(1.5)),
        ),
    }


def run_tornado_analysis(seeds: list, n_steps: int = 252) -> list:
    """
    Runs LOW and HIGH for every tornado parameter on the same matched seeds,
    returns a list of {parameter, low_ci, high_ci, swing} sorted by |swing|
    descending -- the tornado chart's underlying data, largest driver first.
    """
    specs = build_tornado_specs()
    rows = []
    for name, (low_fn, high_fn) in specs.items():
        low_results = _run_scenario(seeds, n_steps, **low_fn())
        high_results = _run_scenario(seeds, n_steps, **high_fn())
        low_ci = _pnl_ci(low_results)
        high_ci = _pnl_ci(high_results)
        swing = (high_ci["mean"] or 0.0) - (low_ci["mean"] or 0.0)
        rows.append({"parameter": name, "low_ci": low_ci, "high_ci": high_ci, "swing": swing})

    rows.sort(key=lambda r: abs(r["swing"]), reverse=True)
    return rows


# ---- priority-overlay strictness: swept continuously, per the roadmap -----

def sweep_overlay_strictness(seeds: list, p_values=None, n_steps: int = 252) -> list:
    """
    Register Section 12.2 / roadmap: sweep priority-overlay strictness `p`
    continuously from 0 to 1, plotting the resulting frontier of dealer P&L
    against military-linked fill rate. Returns a list of
    {p, pnl_ci, military_fill_ci} in ascending p order.
    """
    p_values = p_values if p_values is not None else [0.0, 0.25, 0.5, 0.75, 1.0]
    rows = []
    for p in p_values:
        results = _run_scenario(seeds, n_steps, overlay_p=p)
        pnls = [compute_run_metrics(r)["mark_to_market_pnl"] for r in results]
        mil_fills = [r.get("military_fill_rate") for r in results]
        rows.append({
            "p": p,
            "pnl_ci": confidence_interval(pnls),
            "military_fill_ci": confidence_interval(mil_fills),
        })
    return rows
