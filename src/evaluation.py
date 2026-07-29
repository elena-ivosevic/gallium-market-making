"""
evaluation.py
=============

Phase 8 deliverable: Statistical Rigor. Ensures policy comparisons in this
project are not artifacts of a single lucky (or unlucky) random simulation.

WHAT THIS MODULE DOES
------------------------
- `run_matched_seeds`: runs the SAME policy across many seeds.
- `run_matched_comparison`: runs MULTIPLE policies across the SAME set of
  seeds, so every policy faces identical price paths, regime paths,
  shipment outcomes, and customer-order paths for a given seed (matched
  Monte Carlo) -- guaranteed by this project's existing seed-derivation
  scheme (src/simulation.py seeds price/demand/supply-chain/regime/overlay
  as fixed offsets from one base seed, so two policies run with the same
  base seed see identical exogenous randomness regardless of how each
  policy's own decisions differ).
- `confidence_interval`: mean, std, and a t-distribution confidence
  interval for any metric across seeds.
- `paired_comparison`: because every policy in a matched run faces
  IDENTICAL paths, differences between two policies' per-seed results are
  paired observations -- a paired t-test (not an unpaired/independent-
  samples test) is the statistically correct comparison, and is
  substantially more powerful than an unpaired test at the same sample size
  precisely because it removes path-to-path variation that both policies
  shared.
- `format_headline`: enforces this project's own mastery-checkpoint rule --
  never state a bare number ("Policy A earns $12,000 more"); always attach
  a confidence interval.

WHY MATCHED SEEDS, NOT JUST "RUN EACH POLICY A LOT"
--------------------------------------------------------
Running Policy A on seeds 1-50 and Policy B on seeds 51-100 would still let
you compute a mean and a CI for each -- but comparing them would conflate
"the policies really differ" with "the two seed sets happened to draw
different price/demand paths." Running BOTH policies on the identical
seeds 1-50 eliminates that confound entirely: any difference in outcomes is
attributable only to how the policies actually behaved, not to which random
paths each happened to see.

WHY A PAIRED TEST, NOT AN INDEPENDENT-SAMPLES TEST
--------------------------------------------------------
An unpaired test asks "do these two samples come from different
distributions," treating all the cross-seed variance as noise. A paired
test asks "does the WITHIN-SEED difference tend to be positive or
negative," which is the actual question a matched Monte Carlo design is
built to answer, and uses the pairing to cancel out shared path-to-path
variance rather than average over it.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Confidence intervals here use the t-distribution approximation (adequate
  for the seed counts used in this project's own reports, 30-50 per
  comparison), not a bootstrap or an exact finite-sample method.
- "Emergency procurement cost" is reported via two existing, imprecise
  proxies (register Section 15) rather than a single precisely-tracked
  dollar figure -- see the register for why this project chose not to
  retrofit accounting.py mid-phase rather than paper over the gap.
- Every confidence interval and paired test here is only as trustworthy as
  the underlying simulation's own documented assumptions and limitations
  (Sections 1-14) -- Phase 8 makes existing comparisons statistically
  honest; it does not make the underlying model more realistic.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Every policy comparison earlier in this project (Phase 2's AS calibration
finding, Phase 5's policy comparison, Phase 6's DP result, Phase 7's sector
breakdown) would remain exactly what they currently are: single-seed-set,
non-statistical observations, explicitly flagged throughout as needing this
phase's treatment before being read as more than a first data point.
"""

from dataclasses import dataclass
import numpy as np
from scipy import stats


# ---- per-run metric extraction ---------------------------------------------

def compute_run_metrics(result: dict) -> dict:
    """
    Extracts the roadmap's requested scalar metrics from one
    `Simulation.run()` result dict. Works whether or not supply-chain/regime
    mode was active (fields default to None where not applicable).
    """
    n_orders = result.get("n_orders", 0)
    fill_rate = (result["n_filled"] / n_orders) if n_orders else None

    stockout_occurred = None
    max_drawdown_kg = None
    if "tranche_history" in result:
        available = [row["available_kg"] for row in result["tranche_history"]]
        stockout_occurred = any(a < 0 for a in available)

        physical = [row["physical_kg"] for row in result["tranche_history"]]
        peak = physical[0] if physical else 0.0
        max_drawdown = 0.0
        for v in physical:
            peak = max(peak, v)
            max_drawdown = max(max_drawdown, peak - v)
        max_drawdown_kg = max_drawdown

    return {
        "mark_to_market_pnl": result.get("mark_to_market_pnl"),
        "terminal_wealth": result.get("terminal_wealth"),
        "fill_rate": fill_rate,
        "military_fill_rate": result.get("military_fill_rate"),
        "civilian_fill_rate": result.get("civilian_fill_rate"),
        "stockout_occurred": stockout_occurred,
        "emergency_orders_placed": result.get("emergency_orders_placed"),
        "cumulative_lost_delivery_cost": result.get("cumulative_lost_delivery_cost"),
        "max_drawdown_kg": max_drawdown_kg,
    }


# ---- matched Monte Carlo running --------------------------------------------

def run_matched_seeds(policy_factory, seeds, simulation_cls, **sim_kwargs) -> list:
    """
    Runs a FRESH policy instance (via `policy_factory()`, a zero-arg
    callable) for each seed in `seeds`, using `simulation_cls` (pass
    `src.simulation.Simulation`) with `sim_kwargs` forwarded to its
    constructor. A fresh policy per seed matters because several policies
    in this project carry mutable per-run state (diagnostics, RNGs) that
    must not leak across runs.

    Accepts either `n_steps=<int>` (a new SimulationConfig is built fresh
    per seed) or a pre-built `config=<SimulationConfig>` (its `.seed` is
    overwritten per iteration, and a NEW config object is constructed each
    time from the template's `n_steps` -- never mutating and reusing one
    shared config instance across seeds).
    """
    from src.simulation import SimulationConfig

    template_config = sim_kwargs.pop("config", None)
    n_steps = sim_kwargs.pop("n_steps", template_config.n_steps if template_config else 252)

    results = []
    for seed in seeds:
        config = SimulationConfig(n_steps=n_steps, seed=seed)
        policy = policy_factory()
        sim = simulation_cls(policy, config=config, **sim_kwargs)
        results.append(sim.run())
    return results


def run_matched_comparison(policy_factories: dict, seeds, simulation_cls, **sim_kwargs) -> dict:
    """
    Runs EVERY policy in `policy_factories` (name -> zero-arg factory) across
    the SAME `seeds`, guaranteeing matched paths per seed (see module
    docstring). Returns {"raw_results": {name: [result, ...]},
    "metrics": {name: [metrics_dict, ...]}}.
    """
    raw_results = {}
    metrics = {}
    for name, factory in policy_factories.items():
        results = run_matched_seeds(factory, seeds, simulation_cls, **sim_kwargs)
        raw_results[name] = results
        metrics[name] = [compute_run_metrics(r) for r in results]
    return {"raw_results": raw_results, "metrics": metrics}


# ---- confidence intervals and paired tests ----------------------------------

def confidence_interval(values: list, confidence: float = 0.95) -> dict:
    """
    Mean, std, n, and a t-distribution confidence interval for `values`
    (None entries are dropped, e.g. from seeds where a rate was undefined
    because no orders of that type arrived).
    """
    clean = [v for v in values if v is not None]
    n = len(clean)
    if n == 0:
        return {"mean": None, "std": None, "n": 0, "ci_lower": None, "ci_upper": None}
    mean = float(np.mean(clean))
    if n == 1:
        return {"mean": mean, "std": 0.0, "n": 1, "ci_lower": mean, "ci_upper": mean}
    std = float(np.std(clean, ddof=1))
    sem = std / np.sqrt(n)
    t_crit = stats.t.ppf(0.5 + confidence / 2.0, df=n - 1)
    return {
        "mean": mean, "std": std, "n": n,
        "ci_lower": mean - t_crit * sem, "ci_upper": mean + t_crit * sem,
    }


def tail_loss(values: list, quantile: float = 0.05) -> float | None:
    """Register Section 15: the (default 5th-percentile) quantile of the
    distribution across seeds -- a tail-risk measure, not a CI."""
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return float(np.quantile(clean, quantile))


def paired_comparison(values_a: list, values_b: list, confidence: float = 0.95) -> dict:
    """
    Paired comparison of policy A vs. policy B on the SAME seeds (see module
    docstring for why paired, not independent-samples). `values_a[i]` and
    `values_b[i]` must correspond to the same seed. None entries at matching
    positions are dropped together (a seed missing for one policy is
    excluded from the pair).
    """
    pairs = [(a, b) for a, b in zip(values_a, values_b) if a is not None and b is not None]
    n = len(pairs)
    if n < 2:
        return {"mean_diff": None, "ci_lower": None, "ci_upper": None, "t_stat": None,
                "p_value": None, "n": n}

    diffs = [a - b for a, b in pairs]
    mean_diff = float(np.mean(diffs))
    std_diff = float(np.std(diffs, ddof=1))
    sem = std_diff / np.sqrt(n) if std_diff > 0 else 0.0
    t_crit = stats.t.ppf(0.5 + confidence / 2.0, df=n - 1)

    a_vals = [a for a, _ in pairs]
    b_vals = [b for _, b in pairs]
    if std_diff > 0:
        t_stat, p_value = stats.ttest_rel(a_vals, b_vals)
    else:
        t_stat, p_value = (np.inf if mean_diff != 0 else 0.0), (0.0 if mean_diff != 0 else 1.0)

    return {
        "mean_diff": mean_diff,
        "ci_lower": mean_diff - t_crit * sem,
        "ci_upper": mean_diff + t_crit * sem,
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "n": n,
    }


# ---- the mastery-checkpoint discipline, enforced in code --------------------

def format_headline(label: str, ci: dict, unit: str = "$", decimals: int = 0) -> str:
    """
    Formats a headline comparison the way this project's own mastery
    checkpoint requires: never a bare number. Raises ValueError if `ci`
    doesn't actually contain a computed interval (i.e., this function
    cannot be used to accidentally produce an unqualified claim).
    """
    if ci.get("mean") is None or ci.get("ci_lower") is None or ci.get("ci_upper") is None:
        raise ValueError(
            "format_headline requires a computed confidence interval -- "
            "this project does not report bare numbers for headline comparisons."
        )
    fmt = lambda v: f"{unit}{v:,.{decimals}f}" if unit == "$" else f"{v:.{decimals}f}{unit}"
    return (
        f"{label}: {fmt(ci['mean'])}, with a 95% CI of approximately "
        f"{fmt(ci['ci_lower'])} to {fmt(ci['ci_upper'])} (n={ci['n']})"
    )
