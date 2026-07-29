import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.sector_stress_test import (
    compute_sector_fill_stats, compute_coverage_days, compute_shortage_episodes,
    compute_emergency_wtp_stats, compute_sector_stress_report, SectorStressTestParams,
)


def make_order(t, sector, military_linked, filled, fill_type, wtp=364.0, price=350.0, size=25.0):
    return {
        "t": t, "price": price, "ask": 350.0, "size_kg": size,
        "willingness_to_pay": wtp, "military_linked": military_linked,
        "sector": sector, "filled": filled, "fill_type": fill_type,
    }


def test_sector_fill_stats_basic_counts():
    order_log = [
        make_order(0, "semiconductors", False, True, "immediate"),
        make_order(1, "semiconductors", False, False, "rejected"),
        make_order(2, "defense_aerospace", True, True, "backordered"),
    ]
    stats = compute_sector_fill_stats(order_log)
    assert stats["semiconductors"]["n_orders"] == 2
    assert stats["semiconductors"]["n_filled"] == 1
    assert stats["semiconductors"]["fill_rate"] == pytest.approx(0.5)
    assert stats["defense_aerospace"]["n_orders"] == 1
    assert stats["defense_aerospace"]["fill_rate"] == pytest.approx(1.0)


def test_sector_fill_stats_military_civilian_breakdown_within_sector():
    order_log = [
        make_order(0, "defense_aerospace", True, True, "immediate"),
        make_order(1, "defense_aerospace", True, False, "rejected"),
        make_order(2, "defense_aerospace", False, True, "immediate"),
    ]
    stats = compute_sector_fill_stats(order_log)
    da = stats["defense_aerospace"]
    assert da["military"]["n_orders"] == 2
    assert da["military"]["fill_rate"] == pytest.approx(0.5)
    assert da["civilian"]["n_orders"] == 1
    assert da["civilian"]["fill_rate"] == pytest.approx(1.0)


def test_sector_fill_stats_handles_sector_with_no_orders_of_one_channel():
    order_log = [make_order(0, "solar_clean_energy", False, True, "immediate")]
    stats = compute_sector_fill_stats(order_log)
    assert stats["solar_clean_energy"]["military"]["n_orders"] == 0
    assert stats["solar_clean_energy"]["military"]["fill_rate"] is None


def test_coverage_days_uses_trailing_window_not_full_run_average():
    tranche_history = [{"t": t, "physical_kg": 300.0} for t in range(60)]
    order_log = [make_order(t, "semiconductors", False, True, "immediate", size=10.0) for t in range(30)]
    # Orders only in the first 30 days; days 30-59 should show DECREASING
    # consumption in the trailing window as those early orders roll out of it.
    results = compute_coverage_days(tranche_history, order_log, window_days=30)
    day_29_coverage = results[29]["coverage_days"]
    day_59_coverage = results[59]["coverage_days"]  # window [30,59) has zero orders
    assert day_59_coverage is None  # no consumption in the trailing window at all


def test_coverage_days_none_when_no_recent_consumption():
    tranche_history = [{"t": 0, "physical_kg": 100.0}]
    results = compute_coverage_days(tranche_history, [], window_days=30)
    assert results[0]["coverage_days"] is None


def test_shortage_episodes_detects_single_episode():
    tranche_history = [
        {"t": 0, "available_kg": 10.0},
        {"t": 1, "available_kg": -5.0},
        {"t": 2, "available_kg": -3.0},
        {"t": 3, "available_kg": 8.0},
    ]
    episodes = compute_shortage_episodes(tranche_history)
    assert len(episodes) == 1
    assert episodes[0] == {"start_t": 1, "end_t": 2, "duration_days": 2}


def test_shortage_episodes_detects_multiple_separate_episodes():
    tranche_history = [
        {"t": 0, "available_kg": -1.0},
        {"t": 1, "available_kg": 5.0},
        {"t": 2, "available_kg": -1.0},
        {"t": 3, "available_kg": -1.0},
        {"t": 4, "available_kg": -1.0},
        {"t": 5, "available_kg": 5.0},
    ]
    episodes = compute_shortage_episodes(tranche_history)
    assert len(episodes) == 2
    assert episodes[0]["duration_days"] == 1
    assert episodes[1]["duration_days"] == 3


def test_shortage_episode_still_open_at_end_of_run_is_recorded():
    tranche_history = [
        {"t": 0, "available_kg": 5.0},
        {"t": 1, "available_kg": -2.0},
        {"t": 2, "available_kg": -2.0},
    ]
    episodes = compute_shortage_episodes(tranche_history)
    assert len(episodes) == 1
    assert episodes[0] == {"start_t": 1, "end_t": 2, "duration_days": 2}


def test_no_shortage_episodes_when_always_available():
    tranche_history = [{"t": t, "available_kg": 50.0} for t in range(10)]
    assert compute_shortage_episodes(tranche_history) == []


def test_emergency_wtp_stats_separates_emergency_from_other_fill_types():
    order_log = [
        make_order(0, "defense_aerospace", True, True, "emergency_backordered", wtp=420.0, price=350.0),
        make_order(1, "defense_aerospace", True, True, "backordered", wtp=360.0, price=350.0),
        make_order(2, "semiconductors", False, True, "immediate", wtp=355.0, price=350.0),
    ]
    stats = compute_emergency_wtp_stats(order_log)
    assert stats["n_emergency_orders"] == 1
    assert stats["mean_emergency_wtp_premium"] == pytest.approx(420.0 / 350.0 - 1.0)
    # other includes both non-emergency orders
    expected_other = ((360.0 / 350.0 - 1.0) + (355.0 / 350.0 - 1.0)) / 2
    assert stats["mean_other_wtp_premium"] == pytest.approx(expected_other)


def test_emergency_wtp_stats_none_when_no_emergency_orders():
    order_log = [make_order(0, "semiconductors", False, True, "immediate")]
    stats = compute_emergency_wtp_stats(order_log)
    assert stats["n_emergency_orders"] == 0
    assert stats["mean_emergency_wtp_premium"] is None


def test_compute_sector_stress_report_combines_all_four_components():
    result = {
        "order_log": [make_order(0, "semiconductors", False, True, "immediate")],
        "tranche_history": [{"t": 0, "physical_kg": 100.0, "available_kg": 40.0}],
    }
    report = compute_sector_stress_report(result)
    assert "sector_fill_stats" in report
    assert "coverage_days" in report
    assert "shortage_episodes" in report
    assert "emergency_wtp_stats" in report


def test_custom_window_days_param_is_respected():
    params = SectorStressTestParams(coverage_days_window=5)
    tranche_history = [{"t": t, "physical_kg": 100.0, "available_kg": 40.0} for t in range(10)]
    order_log = [make_order(t, "semiconductors", False, True, "immediate", size=10.0) for t in range(10)]
    result = {"order_log": order_log, "tranche_history": tranche_history}
    report = compute_sector_stress_report(result, params=params)
    # With a 5-day window and constant 10kg/day consumption, coverage should
    # be 100 / (5*10/5) = 100/10 = 10 days at any t >= 4
    assert report["coverage_days"][9]["coverage_days"] == pytest.approx(10.0)
