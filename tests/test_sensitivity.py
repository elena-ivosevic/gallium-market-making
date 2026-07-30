import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.sensitivity import (
    build_tornado_specs, run_tornado_analysis, sweep_overlay_strictness, _run_scenario,
)


def test_all_eleven_named_parameters_present():
    specs = build_tornado_specs()
    expected = {
        "risk_aversion", "jump_intensity", "jump_size", "shipment_reliability",
        "shipment_lead_time", "safety_stock", "hawkes_excitation", "hawkes_decay",
        "sector_demand", "replacement_cost_curvature", "military_linked_demand_share",
    }
    assert set(specs.keys()) == expected


def test_tornado_analysis_runs_and_is_sorted_by_swing_magnitude():
    rows = run_tornado_analysis(seeds=[1, 2, 3], n_steps=60)
    assert len(rows) == 11
    swings = [abs(r["swing"]) for r in rows]
    assert swings == sorted(swings, reverse=True)


def test_tornado_rows_include_confidence_intervals_not_bare_numbers():
    rows = run_tornado_analysis(seeds=[1, 2, 3], n_steps=60)
    for row in rows:
        assert "ci_lower" in row["low_ci"]
        assert "ci_upper" in row["high_ci"]


# ---- regression test for the reliability-override bug found while building this module

def test_shipment_reliability_override_actually_changes_results():
    """
    Regression test for a real bug found while building this module: in
    regime mode, SupplyChainParams.reliability is overwritten every day by
    RegimeSwitcher's own reliability dict, so a naive override of
    SupplyChainParams alone had ZERO effect (identical P&L for low and high
    'reliability' settings) until _scaled_reliability_regime_params was
    added to also scale RegimeParams. This test confirms low and high
    genuinely diverge, not just structurally but numerically.
    """
    specs = build_tornado_specs()
    low_kwargs = specs["shipment_reliability"][0]()
    high_kwargs = specs["shipment_reliability"][1]()

    low_results = _run_scenario([1, 2, 3], 60, **low_kwargs)
    high_results = _run_scenario([1, 2, 3], 60, **high_kwargs)

    low_pnls = [r["mark_to_market_pnl"] for r in low_results]
    high_pnls = [r["mark_to_market_pnl"] for r in high_results]
    assert low_pnls != high_pnls  # not merely close -- must not be IDENTICAL


def test_scaled_reliability_regime_params_actually_scales_every_regime():
    from src.sensitivity import _scaled_reliability_regime_params
    from src.regimes import RegimeParams, REGIMES

    baseline = RegimeParams()
    scaled = _scaled_reliability_regime_params(0.5)
    for regime in REGIMES:
        assert scaled.civilian_reliability[regime] == pytest.approx(
            min(1.0, baseline.civilian_reliability[regime] * 0.5)
        )
        assert scaled.military_reliability[regime] == pytest.approx(
            min(1.0, baseline.military_reliability[regime] * 0.5)
        )


def test_scaled_reliability_caps_at_one():
    from src.sensitivity import _scaled_reliability_regime_params
    scaled = _scaled_reliability_regime_params(10.0)  # deliberately absurd multiplier
    assert all(v <= 1.0 for v in scaled.civilian_reliability.values())
    assert all(v <= 1.0 for v in scaled.military_reliability.values())


# ---- overlay strictness sweep -----------------------------------------------

def test_overlay_sweep_covers_requested_p_values_in_order():
    rows = sweep_overlay_strictness(seeds=[1, 2], p_values=[0.0, 0.5, 1.0], n_steps=60)
    assert [r["p"] for r in rows] == [0.0, 0.5, 1.0]


def test_overlay_sweep_reports_both_pnl_and_military_fill_cis():
    rows = sweep_overlay_strictness(seeds=[1, 2], p_values=[0.0, 1.0], n_steps=60)
    for row in rows:
        assert "mean" in row["pnl_ci"]
        assert "mean" in row["military_fill_ci"]


def test_sector_demand_scaling_changes_arrival_rates_not_military_share():
    from src.sensitivity import _scaled_sectors
    from src.demand import DEFAULT_SECTORS
    scaled = _scaled_sectors(0.5)
    for default_s, scaled_s in zip(DEFAULT_SECTORS, scaled):
        assert scaled_s.arrival_rate_per_year == pytest.approx(default_s.arrival_rate_per_year * 0.5)
        assert scaled_s.military_linked_share == default_s.military_linked_share


def test_military_share_scaling_changes_share_not_arrival_rate():
    from src.sensitivity import _scaled_military_share
    from src.demand import DEFAULT_SECTORS
    scaled = _scaled_military_share(1.5)
    for default_s, scaled_s in zip(DEFAULT_SECTORS, scaled):
        assert scaled_s.arrival_rate_per_year == default_s.arrival_rate_per_year
        assert scaled_s.military_linked_share == pytest.approx(
            min(1.0, default_s.military_linked_share * 1.5)
        )
