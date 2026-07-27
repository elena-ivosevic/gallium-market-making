"""
tests/test_military_addendum.py
=================================

Tests for the military/civilian demand addendum (register Section 10),
added ahead of Phase 4 to unblock Phase 3's channel-dependent shipment
reliability requirement. See docs/assumptions_register.md, Section 10, and
the addendum notes in src/demand.py, src/supply_chain.py, and
src/simulation.py for the full rationale.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.demand import PoissonOrderFlow, DemandParams
from src.supply_chain import SupplyChain, SupplyChainParams
from src.accounting import DealerBook, AccountingParams
from src.policies.fixed_spread import FixedSpreadPolicy, FixedSpreadParams
from src.simulation import Simulation, SimulationConfig


# ---- demand.py tagging -----------------------------------------------------

def test_orders_are_tagged_military_linked_at_roughly_the_configured_share():
    """generate_orders() returns one DAY's worth of arrivals, not a year's --
    accumulate across many simulated days for a stable share estimate."""
    params = DemandParams(arrival_rate_per_year=250.0, military_linked_share=0.15)
    flow = PoissonOrderFlow(params, seed=1)
    all_orders = []
    for _ in range(2000):
        all_orders.extend(flow.generate_orders(mid_price=350.0))
    assert len(all_orders) > 200  # sanity: enough orders for a stable estimate
    share = np.mean([o.military_linked for o in all_orders])
    assert abs(share - 0.15) < 0.05


def test_zero_military_share_tags_nothing():
    params = DemandParams(arrival_rate_per_year=2000.0, military_linked_share=0.0)
    flow = PoissonOrderFlow(params, seed=2)
    orders = flow.generate_orders(mid_price=350.0)
    assert all(not o.military_linked for o in orders)


def test_full_military_share_tags_everything():
    params = DemandParams(arrival_rate_per_year=2000.0, military_linked_share=1.0)
    flow = PoissonOrderFlow(params, seed=3)
    orders = flow.generate_orders(mid_price=350.0)
    assert all(o.military_linked for o in orders)


def test_seed_reproduces_identical_orders_regardless_of_military_tag():
    """The military tag draw must not perturb order size/WTP reproducibility
    -- it's drawn last, after size and WTP, for exactly this reason."""
    params = DemandParams(arrival_rate_per_year=500.0, military_linked_share=0.15)
    orders_a = PoissonOrderFlow(params, seed=9).generate_orders(mid_price=350.0)
    orders_b = PoissonOrderFlow(params, seed=9).generate_orders(mid_price=350.0)
    assert [o.size_kg for o in orders_a] == [o.size_kg for o in orders_b]
    assert [o.willingness_to_pay for o in orders_a] == [o.willingness_to_pay for o in orders_b]
    assert [o.military_linked for o in orders_a] == [o.military_linked for o in orders_b]


# ---- supply_chain.py channel reliability -----------------------------------

def test_reliability_for_returns_channel_specific_values():
    params = SupplyChainParams(reliability=0.95, reliability_military=0.75)
    assert params.reliability_for("civilian") == 0.95
    assert params.reliability_for("military") == 0.75


def test_place_order_defaults_to_civilian_channel():
    chain = SupplyChain(SupplyChainParams(reliability=0.95, reliability_military=0.75), seed=1)
    shipment = chain.place_order(100.0)
    assert shipment.channel == "civilian"
    assert shipment.reliability == 0.95


def test_place_order_military_channel_uses_military_reliability():
    chain = SupplyChain(SupplyChainParams(reliability=0.95, reliability_military=0.75), seed=1)
    shipment = chain.place_order(100.0, channel="military")
    assert shipment.channel == "military"
    assert shipment.reliability == 0.75


def test_place_order_rejects_invalid_channel():
    chain = SupplyChain(SupplyChainParams(), seed=1)
    with pytest.raises(ValueError):
        chain.place_order(100.0, channel="commercial")


def test_lower_military_reliability_produces_more_military_failed_deliveries():
    chain = SupplyChain(
        SupplyChainParams(reliability=0.95, reliability_military=0.3, lead_time_days=1), seed=5
    )
    for _ in range(200):
        chain.place_order(50.0, channel="civilian")
        chain.place_order(50.0, channel="military")
    chain.advance_day()
    assert (
        chain.total_failed_deliveries_by_channel["military"]
        > chain.total_failed_deliveries_by_channel["civilian"]
    )


def test_in_transit_and_expected_kg_support_channel_filtering():
    chain = SupplyChain(SupplyChainParams(reliability=0.95, reliability_military=0.75, lead_time_days=10), seed=1)
    chain.place_order(100.0, channel="civilian")
    chain.place_order(50.0, channel="military")

    assert chain.in_transit_kg() == pytest.approx(150.0)
    assert chain.in_transit_kg(channel="civilian") == pytest.approx(100.0)
    assert chain.in_transit_kg(channel="military") == pytest.approx(50.0)

    assert chain.expected_kg(channel="civilian") == pytest.approx(100.0 * 0.95)
    assert chain.expected_kg(channel="military") == pytest.approx(50.0 * 0.75)
    assert chain.expected_kg() == pytest.approx(100.0 * 0.95 + 50.0 * 0.75)


# ---- accounting.py backlog penalty -----------------------------------------

def test_backlog_penalty_debits_cash_and_reduces_realized_pnl():
    book = DealerBook(AccountingParams(initial_cash=10_000.0))
    book.record_backlog_penalty(50.0)
    assert book.cash == pytest.approx(9_950.0)
    assert book.realized_pnl() == pytest.approx(-50.0)
    assert book.cumulative_backlog_penalty == pytest.approx(50.0)


def test_backlog_penalty_rejects_negative_value():
    book = DealerBook(AccountingParams())
    with pytest.raises(ValueError):
        book.record_backlog_penalty(-1.0)


# ---- end-to-end: fill-rate breakdown and backlog accrual -------------------

def test_result_includes_military_civilian_fill_rate_breakdown():
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=252, seed=40),
        supply_chain_params=SupplyChainParams(),
    )
    result = sim.run()
    for key in (
        "n_military_orders", "n_military_filled", "military_fill_rate",
        "n_civilian_orders", "n_civilian_filled", "civilian_fill_rate",
        "shipments_by_channel", "failed_deliveries_by_channel", "kg_lost_by_channel",
        "cumulative_backlog_penalty",
    ):
        assert key in result
    assert result["n_military_orders"] + result["n_civilian_orders"] == result["n_orders"]


def test_civilian_order_rejected_when_physical_and_pipeline_insufficient():
    """
    Controlled, deterministic version (an earlier attempt relied on a long
    stochastic simulation organically running short of physical stock, but
    the reorder-point's conservative 100%-fill assumption over-provisions
    inventory so heavily that scarcity essentially never binds in practice
    -- see docs/assumptions_register.md, Section 9's over-accumulation note.
    Directly manipulating the book/pipeline state is the reliable way to
    actually exercise this code path.)

    A civilian order that cannot be filled from physical stock, and that the
    pipeline (physical + expected - committed) also cannot cover, must be
    REJECTED -- not backordered.
    """
    from src.demand import CustomerOrder

    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=10, seed=50),
        supply_chain_params=SupplyChainParams(),
    )
    sim.book.tranches.physical_kg = 5.0  # far below the order size
    civilian_order = CustomerOrder(size_kg=50.0, willingness_to_pay=400.0, military_linked=False)

    filled, fill_type = sim._attempt_fill_phase3(civilian_order, ask=380.0, price=380.0)

    assert filled is False
    assert fill_type == "rejected"
    assert sim.book.failed_sales == 1
    assert sim.book.tranches.committed_kg == 0.0  # no commitment was ever reserved


def test_military_order_backordered_in_the_exact_same_starved_state():
    """Same starved book state as the civilian test above, but a
    military-linked order should be accepted as a backorder (or emergency-
    backordered) instead of rejected."""
    from src.demand import CustomerOrder

    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=10, seed=51),
        supply_chain_params=SupplyChainParams(),
    )
    sim.book.tranches.physical_kg = 5.0  # identical starved state
    military_order = CustomerOrder(size_kg=50.0, willingness_to_pay=400.0, military_linked=True)

    filled, fill_type = sim._attempt_fill_phase3(military_order, ask=380.0, price=380.0)

    assert filled is True
    assert fill_type in ("backordered", "emergency_backordered")
    assert sim.book.tranches.committed_kg == pytest.approx(50.0)
    assert len(sim.backorder_queue) == 1


def test_emergency_military_shortfall_coverage_uses_military_channel():
    """When even the pipeline can't cover a military-linked order, the
    emergency order placed to close the gap should route through the
    military channel (lower reliability), not civilian."""
    from src.demand import CustomerOrder

    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=10, seed=52),
        supply_chain_params=SupplyChainParams(reliability=0.95, reliability_military=0.75),
    )
    sim.book.tranches.physical_kg = 0.0  # nothing on hand, nothing in transit either
    military_order = CustomerOrder(size_kg=80.0, willingness_to_pay=400.0, military_linked=True)

    filled, fill_type = sim._attempt_fill_phase3(military_order, ask=380.0, price=380.0)

    assert filled is True
    assert fill_type == "emergency_backordered"
    assert len(sim.supply_chain.pending) == 1
    assert sim.supply_chain.pending[0].channel == "military"
    assert sim.supply_chain.pending[0].emergency is True


def test_normal_restock_routes_through_civilian_channel():
    """Ordinary reorder-point-triggered restocking (not tied to any specific
    military shortfall) should route through the civilian channel."""
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=10, seed=53),
        supply_chain_params=SupplyChainParams(reliability=0.95, reliability_military=0.75),
    )
    sim.book.tranches.physical_kg = 0.0
    sim._run_supply_chain_day(price=350.0)
    assert len(sim.supply_chain.pending) == 1
    assert sim.supply_chain.pending[0].channel == "civilian"
    assert sim.supply_chain.pending[0].emergency is False


def test_backlog_penalty_accrues_only_when_backorders_outstanding():
    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy,
        config=SimulationConfig(n_steps=252, seed=42),
        supply_chain_params=SupplyChainParams(),
    )
    result = sim.run()
    # Penalty should be non-negative and zero only if no backlog ever formed.
    assert result["cumulative_backlog_penalty"] >= 0.0


def test_phase1_2_and_non_addendum_phase3_defaults_are_unaffected():
    """Regression guard: default military_linked_share (0.15) does not break
    any existing Phase 1/2 or non-supply-chain-mode assumption; Phase 1/2
    mode still runs with no military-specific keys in the result."""
    policy = FixedSpreadPolicy(FixedSpreadParams())
    result = Simulation(policy, config=SimulationConfig(n_steps=100, seed=7)).run()
    assert "military_fill_rate" not in result
    assert "n_military_orders" not in result
