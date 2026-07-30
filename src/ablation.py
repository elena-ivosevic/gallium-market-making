"""
ablation.py
============

Phase 9 deliverable: Ablation Study. Actually runs the ablation table that
was PRE-REGISTERED back in Phase 5 (docs/assumptions_register.md, Section
12.3), before this phase existed -- so these results confirm or overturn a
stated prior, not a post-hoc pattern-match.

WHAT THIS MODULE DOES
------------------------
Builds nine "variants" of the full model, each removing (or in one case,
regressing to a strictly simpler predecessor) exactly ONE component,
holding everything else fixed:

    full_model                    -- everything on (register Section 12.3's baseline)
    no_hawkes                     -- Hawkes excitation forced to zero in every regime
    no_regime_switching           -- regime pinned at Normal forever (never transitions)
    no_shipment_risk_premium      -- scarcity-AS with shipment_risk_gamma = 0
    no_replacement_cost_premium   -- scarcity-AS with replacement_cost_pass_through = 0
    no_commitment_premium         -- scarcity-AS with commitment_gamma = 0
    no_scarcity_premium           -- scarcity-AS with scarcity_gamma = 0
    no_priority_overlay           -- priority overlay strictness p = 0 instead of 1
    standard_AS                   -- plain Avellaneda-Stoikov (Phase 2), no premiums, no overlay

Then runs every variant on the SAME matched seeds (src/evaluation.py) and
reports each one's metrics alongside the FULL model's, so the marginal
effect of removing each single component is directly comparable.

WHY "NO REGIME SWITCHING" PINS AT NORMAL, RATHER THAN REMOVING REGIMES ENTIRELY
------------------------------------------------------------------------------------
Passing `regime_params=None` would also revert demand to Phase 1-3's flat
aggregate Poisson process (losing sectors, Hawkes, and military elasticity
all at once) -- conflating "no regime SWITCHING" with "no regime machinery
of any kind," which is a different, much bigger ablation than the roadmap
asks for. Pinning the regime at Normal forever (self-transition = 1.0)
isolates regime switching specifically: sectors, Hawkes, and the reliability
mechanism all still exist, they just never see anything but Normal
conditions. This also reuses the exact "Normal regime only" edge case the
roadmap's own Phase 10 validation checklist calls for.

WHY "NO HAWKES" ZEROES EXCITATION RATHER THAN REMOVING THE SECTOR/REGIME MACHINERY
----------------------------------------------------------------------------------------
Same principle: `RegimeParams.hawkes_excitation` set to zero in every regime
removes ONLY the self-exciting clustering term (src/demand.py's
`SectorHawkesOrderFlow` reduces to plain per-sector Poisson arrivals), while
sectors, regimes, and reliability all remain exactly as in the full model.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- These nine variants are each a SINGLE-component ablation; this module does
  not test combinations of removals (e.g., "no Hawkes AND no scarcity
  premium together") -- register Section 16 flags this as a natural
  follow-up, not attempted here to keep the comparison count (and runtime)
  bounded.
- "no_regime_switching" and "no_hawkes" still run in supply-chain mode with
  a full default SupplyChainParams() and AccountingParams() -- only the
  specifically-named mechanism is removed, per component-isolation logic
  above.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Phase 5's pre-registered ablation table (register Section 12.3) would
remain a set of predictions no one ever actually tested against this
project's own simulation.
"""

from src.policies.avellaneda_stoikov import AvellanedaStoikovPolicy, AvellanedaStoikovParams
from src.policies.scarcity_adjusted_as import ScarcityAdjustedASPolicy, ScarcityAdjustedASParams
from src.policies.priority_overlay import PriorityOverlayParams
from src.regimes import RegimeParams
from src.accounting import AccountingParams
from src.simulation import Simulation, SimulationConfig
from src.evaluation import compute_run_metrics


def _no_switching_regime_params() -> RegimeParams:
    p = RegimeParams(initial_regime="normal")
    p.transition_matrix = {
        "normal": {"normal": 1.0, "delayed": 0.0, "severe": 0.0, "recovery": 0.0},
        "delayed": dict(p.transition_matrix["delayed"]),
        "severe": dict(p.transition_matrix["severe"]),
        "recovery": dict(p.transition_matrix["recovery"]),
    }
    return p


def _no_hawkes_regime_params() -> RegimeParams:
    p = RegimeParams()
    p.hawkes_excitation = {k: 0.0 for k in p.hawkes_excitation}
    return p


def build_ablation_variants() -> dict:
    """
    Returns {variant_name: (policy_factory, extra_sim_kwargs)}. Each factory
    and kwargs dict is freshly constructed per call, and this function
    itself builds fresh objects per variant (no shared mutable RegimeParams/
    PriorityOverlayParams instances across variants).
    """
    return {
        "full_model": (
            lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams()),
            dict(regime_params=RegimeParams(), priority_overlay_params=PriorityOverlayParams(p=1.0)),
        ),
        "no_hawkes": (
            lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams()),
            dict(regime_params=_no_hawkes_regime_params(),
                 priority_overlay_params=PriorityOverlayParams(p=1.0)),
        ),
        "no_regime_switching": (
            lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams()),
            dict(regime_params=_no_switching_regime_params(),
                 priority_overlay_params=PriorityOverlayParams(p=1.0)),
        ),
        "no_shipment_risk_premium": (
            lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams(shipment_risk_gamma=0.0)),
            dict(regime_params=RegimeParams(), priority_overlay_params=PriorityOverlayParams(p=1.0)),
        ),
        "no_replacement_cost_premium": (
            lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams(replacement_cost_pass_through=0.0)),
            dict(regime_params=RegimeParams(), priority_overlay_params=PriorityOverlayParams(p=1.0)),
        ),
        "no_commitment_premium": (
            lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams(commitment_gamma=0.0)),
            dict(regime_params=RegimeParams(), priority_overlay_params=PriorityOverlayParams(p=1.0)),
        ),
        "no_scarcity_premium": (
            lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams(scarcity_gamma=0.0)),
            dict(regime_params=RegimeParams(), priority_overlay_params=PriorityOverlayParams(p=1.0)),
        ),
        "no_priority_overlay": (
            lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams()),
            dict(regime_params=RegimeParams(), priority_overlay_params=PriorityOverlayParams(p=0.0)),
        ),
        "standard_AS": (
            lambda: AvellanedaStoikovPolicy(AvellanedaStoikovParams()),
            dict(regime_params=RegimeParams()),
        ),
    }


def run_ablation_study(seeds: list, n_steps: int = 252, safety_stock_kg: float = 60.0) -> dict:
    """
    Runs every ablation variant on the SAME `seeds` (matched Monte Carlo,
    src/evaluation.py). Returns {"raw_results": {variant: [result, ...]},
    "metrics": {variant: [metrics_dict, ...]}}.
    """
    variants = build_ablation_variants()
    accounting_params = AccountingParams(safety_stock_kg=safety_stock_kg)

    raw_results, metrics = {}, {}
    for name, (factory, extra_kwargs) in variants.items():
        results = []
        for seed in seeds:
            policy = factory()
            sim = Simulation(
                policy, config=SimulationConfig(n_steps=n_steps, seed=seed),
                accounting_params=accounting_params, **extra_kwargs,
            )
            results.append(sim.run())
        raw_results[name] = results
        metrics[name] = [compute_run_metrics(r) for r in results]

    return {"raw_results": raw_results, "metrics": metrics}
