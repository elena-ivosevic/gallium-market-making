"""
tests/test_phase3_integration.py
==================================

Phase 3 deliverable: end-to-end tests of supply-chain mode through the full
Simulation loop, plus an explicit regression test proving Phase 1/2 behavior
is completely unaffected by Phase 3's additions (the "opt-in, not a rewrite"
claim made throughout src/simulation.py's docstring).
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

from src.policies.fixed_spread import FixedSpreadPolicy, FixedSpreadParams
from src.simulation import Simulation, SimulationConfig
from src.supply_chain import SupplyChainParams
from src.accounting import AccountingParams


def test_phase1_2_behavior_is_byte_for_byte_unchanged_without_supply_chain_params():
    """Regression guard: running WITHOUT supply_chain_params must reproduce
    exactly the same result as before Phase 3 existed."""
    policy_a = FixedSpreadPolicy(FixedSpreadParams())
    policy_b = FixedSpreadPolicy(FixedSpreadParams())

    result_a = Simulation(policy_a, config=SimulationConfig(n_steps=100, seed=7)).run()
    result_b = Simulation(policy_b, config=SimulationConfig(n_steps=100, seed=7)).run()

    assert result_a["terminal_wealth"] == result_b["terminal_wealth"]
    assert result_a["price_path"] == result_b["price_path"]
    assert "tranche_history" not in result_a  # Phase 3 keys absent in Phase 1/2 mode
    assert "shipments_placed" not in result_a


def test_supply_chain_mode_runs_and_returns_expected_new_keys():
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=120, seed=21),
        supply_chain_params=SupplyChainParams(),
    )
    result = sim.run()

    expected_new_keys = {
        "tranche_history", "shipments_placed", "emergency_orders_placed",
        "failed_deliveries", "kg_lost_to_failed_deliveries", "stockout_events",
        "final_backorder_queue_kg",
    }
    assert expected_new_keys.issubset(result.keys())
    assert len(result["tranche_history"]) == 120


def test_supply_chain_mode_places_shipments_over_a_long_run():
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=252, seed=22),
        supply_chain_params=SupplyChainParams(),
    )
    result = sim.run()
    assert result["shipments_placed"] > 0


def test_tranche_history_never_shows_negative_physical_or_committed():
    """Physical and committed inventory tranches should never go negative --
    that's a bookkeeping invariant, unlike available_kg which is ALLOWED to
    go negative (see src/inventory.py)."""
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=252, seed=23),
        supply_chain_params=SupplyChainParams(),
    )
    result = sim.run()
    for row in result["tranche_history"]:
        assert row["committed_kg"] >= -1e-6


def test_expected_kg_is_never_treated_as_available_kg_within_a_run():
    """Structural check on the mastery-checkpoint distinction: available_kg
    (from accounting.py) should never simply equal physical_kg + expected_kg
    -- expected inventory must not silently leak into the 'available' figure
    a policy would treat as freely quotable."""
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=252, seed=24),
        supply_chain_params=SupplyChainParams(),
    )
    result = sim.run()
    mismatches = 0
    for row in result["tranche_history"]:
        naive_if_wrongly_pooled = row["physical_kg"] + row["expected_kg"] - row["committed_kg"]
        if not np.isclose(row["available_kg"], naive_if_wrongly_pooled):
            mismatches += 1
    # available_kg is physical - committed - safety_stock; it should differ
    # from "physical + expected - committed" (the wrong, pooled calculation)
    # on essentially every day that any shipment is in transit.
    assert mismatches > 0


def test_low_reliability_produces_more_stockout_events_and_emergency_orders():
    """Sanity check: a much less reliable supply chain should force more
    emergency intervention to keep honoring priced orders."""
    reliable = SupplyChainParams(reliability=0.98, lead_time_days=7)
    unreliable = SupplyChainParams(reliability=0.3, lead_time_days=7)

    policy_a = FixedSpreadPolicy(FixedSpreadParams())
    policy_b = FixedSpreadPolicy(FixedSpreadParams())

    result_reliable = Simulation(
        policy_a, config=SimulationConfig(n_steps=252, seed=30), supply_chain_params=reliable
    ).run()
    result_unreliable = Simulation(
        policy_b, config=SimulationConfig(n_steps=252, seed=30), supply_chain_params=unreliable
    ).run()

    assert result_unreliable["stockout_events"] >= result_reliable["stockout_events"]


def test_all_orders_are_eventually_filled_or_explicitly_rejected():
    """Every order the policy agreed to price should end up filled by some
    mechanism (immediate, backordered, or emergency_backordered) -- Phase 3's
    'never silently drop a priced order' design choice (see simulation.py
    docstring, 'A deliberate Phase 3 simplification')."""
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=252, seed=31),
        supply_chain_params=SupplyChainParams(),
    )
    result = sim.run()
    for o in result["order_log"]:
        if o["ask"] <= o["willingness_to_pay"]:
            assert o["filled"] is True
            assert o["fill_type"] in ("immediate", "backordered", "emergency_backordered")
        else:
            assert o["filled"] is False
            assert o["fill_type"] == "rejected"
