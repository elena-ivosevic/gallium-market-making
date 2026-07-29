import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.evaluation import (
    compute_run_metrics, run_matched_seeds, run_matched_comparison,
    confidence_interval, paired_comparison, tail_loss, format_headline,
)
from src.policies.fixed_spread import FixedSpreadPolicy, FixedSpreadParams
from src.policies.scarcity_adjusted_as import ScarcityAdjustedASPolicy, ScarcityAdjustedASParams
from src.simulation import Simulation, SimulationConfig
from src.regimes import RegimeParams


# ---- confidence_interval -----------------------------------------------------

def test_confidence_interval_matches_known_manual_calculation():
    """A small, hand-checkable dataset: mean and CI computed against a known
    t-distribution result."""
    from scipy import stats
    values = [10.0, 12.0, 9.0, 11.0, 13.0, 8.0, 14.0]
    ci = confidence_interval(values, confidence=0.95)
    expected_mean = np.mean(values)
    expected_std = np.std(values, ddof=1)
    sem = expected_std / np.sqrt(len(values))
    t_crit = stats.t.ppf(0.975, df=len(values) - 1)
    assert ci["mean"] == pytest.approx(expected_mean)
    assert ci["ci_lower"] == pytest.approx(expected_mean - t_crit * sem)
    assert ci["ci_upper"] == pytest.approx(expected_mean + t_crit * sem)


def test_confidence_interval_drops_none_values():
    ci = confidence_interval([1.0, None, 2.0, None, 3.0])
    assert ci["n"] == 3
    assert ci["mean"] == pytest.approx(2.0)


def test_confidence_interval_empty_returns_none():
    ci = confidence_interval([None, None])
    assert ci["mean"] is None
    assert ci["n"] == 0


def test_confidence_interval_single_value_has_zero_width():
    ci = confidence_interval([5.0])
    assert ci["mean"] == 5.0
    assert ci["ci_lower"] == ci["ci_upper"] == 5.0


def test_wider_variance_produces_wider_interval():
    tight = confidence_interval([10.0, 10.1, 9.9, 10.0, 10.05] * 4)
    wide = confidence_interval([0.0, 20.0, 5.0, 15.0, 10.0] * 4)
    assert (wide["ci_upper"] - wide["ci_lower"]) > (tight["ci_upper"] - tight["ci_lower"])


# ---- paired_comparison --------------------------------------------------------

def test_paired_comparison_detects_a_consistent_difference():
    """Policy A consistently 10 units better than B on every matched seed --
    should show a clean, significant difference."""
    a = [110.0, 108.0, 112.0, 109.0, 111.0, 107.0]
    b = [100.0, 98.0, 102.0, 99.0, 101.0, 97.0]
    result = paired_comparison(a, b)
    assert result["mean_diff"] == pytest.approx(10.0)
    assert result["ci_lower"] > 0  # entirely positive -- a genuine difference
    assert result["p_value"] < 0.05


def test_paired_comparison_no_difference_gives_high_p_value():
    a = [100.0, 95.0, 105.0, 98.0, 102.0, 99.0]
    b = [101.0, 94.0, 104.0, 99.0, 101.0, 100.0]  # essentially the same, noisy
    result = paired_comparison(a, b)
    assert result["p_value"] > 0.05


def test_paired_comparison_drops_unmatched_none_entries():
    a = [10.0, None, 20.0, 30.0]
    b = [5.0, 100.0, None, 25.0]
    result = paired_comparison(a, b)
    assert result["n"] == 2  # only indices 0 and 3 have both defined


def test_paired_comparison_too_few_pairs_returns_none():
    result = paired_comparison([1.0], [2.0])
    assert result["mean_diff"] is None
    assert result["n"] == 1


def test_paired_comparison_identical_values_gives_zero_diff_and_high_p():
    a = [5.0, 5.0, 5.0, 5.0]
    b = [5.0, 5.0, 5.0, 5.0]
    result = paired_comparison(a, b)
    assert result["mean_diff"] == pytest.approx(0.0)
    assert result["p_value"] == pytest.approx(1.0)


# ---- tail_loss ----------------------------------------------------------------

def test_tail_loss_returns_expected_quantile():
    values = list(range(1, 101))  # 1..100
    result = tail_loss([float(v) for v in values], quantile=0.05)
    assert result == pytest.approx(np.quantile(values, 0.05))


def test_tail_loss_none_when_empty():
    assert tail_loss([]) is None


# ---- format_headline: enforces the mastery-checkpoint discipline -----------

def test_format_headline_requires_a_computed_ci():
    with pytest.raises(ValueError):
        format_headline("Test", {"mean": None, "ci_lower": None, "ci_upper": None, "n": 0})


def test_format_headline_includes_mean_and_both_bounds():
    ci = {"mean": 12000.0, "ci_lower": 8000.0, "ci_upper": 16000.0, "n": 30}
    headline = format_headline("Policy A improves average terminal P&L by", ci)
    assert "$12,000" in headline
    assert "$8,000" in headline
    assert "$16,000" in headline
    assert "95% CI" in headline


# ---- compute_run_metrics -------------------------------------------------------

def test_compute_run_metrics_extracts_pnl_and_fill_rate():
    fake_result = {"mark_to_market_pnl": 5000.0, "terminal_wealth": 55000.0,
                   "n_orders": 100, "n_filled": 40}
    metrics = compute_run_metrics(fake_result)
    assert metrics["mark_to_market_pnl"] == 5000.0
    assert metrics["fill_rate"] == pytest.approx(0.4)


def test_compute_run_metrics_detects_stockout_from_tranche_history():
    fake_result = {
        "n_orders": 0, "n_filled": 0,
        "tranche_history": [{"available_kg": 10.0, "physical_kg": 50.0},
                             {"available_kg": -5.0, "physical_kg": 40.0}],
    }
    metrics = compute_run_metrics(fake_result)
    assert metrics["stockout_occurred"] is True


def test_compute_run_metrics_no_stockout_when_always_available():
    fake_result = {
        "n_orders": 0, "n_filled": 0,
        "tranche_history": [{"available_kg": 10.0, "physical_kg": 50.0},
                             {"available_kg": 5.0, "physical_kg": 40.0}],
    }
    metrics = compute_run_metrics(fake_result)
    assert metrics["stockout_occurred"] is False


def test_compute_run_metrics_max_drawdown_reflects_peak_to_trough_decline():
    fake_result = {
        "n_orders": 0, "n_filled": 0,
        "tranche_history": [
            {"available_kg": 0, "physical_kg": 100.0},
            {"available_kg": 0, "physical_kg": 150.0},  # new peak
            {"available_kg": 0, "physical_kg": 30.0},   # drawdown of 120 from peak
            {"available_kg": 0, "physical_kg": 200.0},  # new peak
        ],
    }
    metrics = compute_run_metrics(fake_result)
    assert metrics["max_drawdown_kg"] == pytest.approx(120.0)


# ---- run_matched_seeds / run_matched_comparison: real integration ----------

def test_run_matched_seeds_uses_identical_price_paths_across_seeds_correctly():
    """Same seed given to two separate calls should reproduce identical results."""
    results_a = run_matched_seeds(
        lambda: FixedSpreadPolicy(FixedSpreadParams()), [7], Simulation, n_steps=100
    )
    results_b = run_matched_seeds(
        lambda: FixedSpreadPolicy(FixedSpreadParams()), [7], Simulation, n_steps=100
    )
    assert results_a[0]["terminal_wealth"] == results_b[0]["terminal_wealth"]


def test_run_matched_comparison_gives_policies_identical_price_paths_per_seed():
    """The core matched-Monte-Carlo guarantee: two different policies on the
    same seed must see the identical price path."""
    factories = {
        "fixed": lambda: FixedSpreadPolicy(FixedSpreadParams()),
        "scarcity": lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams()),
    }
    comparison = run_matched_comparison(factories, [3, 4], Simulation, n_steps=100)
    price_path_fixed = comparison["raw_results"]["fixed"][0]["price_path"]
    price_path_scarcity = comparison["raw_results"]["scarcity"][0]["price_path"]
    assert price_path_fixed == price_path_scarcity


def test_run_matched_comparison_returns_metrics_for_every_policy():
    factories = {
        "fixed": lambda: FixedSpreadPolicy(FixedSpreadParams()),
        "scarcity": lambda: ScarcityAdjustedASPolicy(ScarcityAdjustedASParams()),
    }
    comparison = run_matched_comparison(
        factories, [1, 2, 3], Simulation, n_steps=100, regime_params=RegimeParams()
    )
    assert len(comparison["metrics"]["fixed"]) == 3
    assert len(comparison["metrics"]["scarcity"]) == 3
    assert "mark_to_market_pnl" in comparison["metrics"]["fixed"][0]
