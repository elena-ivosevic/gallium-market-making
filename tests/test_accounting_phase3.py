import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.accounting import DealerBook, AccountingParams


def make_book(**overrides):
    params = AccountingParams(**overrides) if overrides else AccountingParams()
    return DealerBook(params)


def test_inventory_kg_property_matches_tranches_physical_kg():
    """Backward-compatibility check: inventory_kg must behave exactly like
    the old plain float, now backed by tranches.physical_kg."""
    book = make_book(initial_inventory_kg=150.0)
    assert book.inventory_kg == 150.0
    book.inventory_kg = 90.0
    assert book.tranches.physical_kg == 90.0
    book.inventory_kg -= 10.0
    assert book.inventory_kg == 80.0
    assert book.tranches.physical_kg == 80.0


def test_pay_for_supply_order_debits_cash_without_touching_inventory():
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=50.0)
    cost = book.pay_for_supply_order(kg=100.0, unit_cost=320.0)
    assert cost == pytest.approx(32_000.0)
    assert book.cash == pytest.approx(10_000.0 - 32_000.0)
    assert book.inventory_kg == 50.0  # unchanged -- kg is in-transit, not physical yet
    assert book.cumulative_replacement_cost == pytest.approx(32_000.0)


def test_receive_delivery_increases_physical_and_updates_cost_basis_using_locked_cost():
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=0.0)
    book.receive_delivery(kg=100.0, unit_cost=330.0)  # locked-in cost, not current spot
    assert book.inventory_kg == pytest.approx(100.0)
    assert book.avg_cost_basis == pytest.approx(330.0)
    assert book.cash == 10_000.0  # cash already debited earlier via pay_for_supply_order


def test_receive_delivery_blends_cost_basis_with_existing_physical_stock():
    book = make_book(initial_cash=0.0, initial_inventory_kg=0.0)
    book.receive_delivery(kg=100.0, unit_cost=300.0)
    book.receive_delivery(kg=100.0, unit_cost=340.0)
    assert book.inventory_kg == pytest.approx(200.0)
    assert book.avg_cost_basis == pytest.approx((100 * 300.0 + 100 * 340.0) / 200.0)


def test_reserve_and_deliver_against_commitment_recognizes_revenue_only_at_delivery():
    book = make_book(initial_cash=0.0, initial_inventory_kg=0.0)
    book.reserve_commitment(50.0)
    assert book.committed_kg == 50.0
    assert book.cumulative_revenue == 0.0  # nothing recognized yet -- only promised

    book.receive_delivery(kg=50.0, unit_cost=300.0)  # stock physically arrives
    delivered = book.deliver_against_commitment(kg=50.0, price=360.0)

    assert delivered == pytest.approx(50.0)
    assert book.committed_kg == 0.0
    assert book.inventory_kg == pytest.approx(0.0)  # consumed by the commitment
    assert book.cumulative_revenue == pytest.approx(50.0 * 360.0)
    assert book.cash == pytest.approx(50.0 * 360.0)


def test_deliver_against_commitment_caps_at_outstanding_commitment_and_physical_stock():
    book = make_book(initial_cash=0.0, initial_inventory_kg=0.0)
    book.reserve_commitment(30.0)
    book.receive_delivery(kg=100.0, unit_cost=300.0)  # more physical stock than owed

    delivered = book.deliver_against_commitment(kg=100.0, price=360.0)  # ask for more than owed
    assert delivered == pytest.approx(30.0)  # capped at the commitment
    assert book.committed_kg == 0.0
    assert book.inventory_kg == pytest.approx(70.0)  # only 30kg consumed, 70kg remains free


def test_available_kg_reflects_commitments_and_safety_stock():
    book = make_book(initial_inventory_kg=200.0, safety_stock_kg=60.0)
    book.reserve_commitment(50.0)
    assert book.available_kg() == pytest.approx(200.0 - 50.0 - 60.0)


def test_snapshot_includes_phase3_fields():
    book = make_book(initial_inventory_kg=200.0, safety_stock_kg=60.0)
    book.reserve_commitment(20.0)
    row = book.snapshot(t=0, price=350.0)
    assert row["committed_kg"] == pytest.approx(20.0)
    assert row["available_kg"] == pytest.approx(200.0 - 20.0 - 60.0)


def test_phase1_restock_methods_still_work_unchanged():
    """Regression guard: Phase 1's instant-restock stub must remain fully
    functional even though Phase 3 adds a parallel supply-chain path."""
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=0.0)
    cost = book.restock(kg=50.0, spot_price=300.0, markup_frac=0.10)
    assert book.inventory_kg == pytest.approx(50.0)
    assert cost == pytest.approx(50.0 * 300.0 * 1.10)
    assert book.restock_events == 1


def test_lost_delivery_cost_reduces_realized_pnl():
    """The accounting-completeness fix: cash paid for kg that never arrived
    must show up as a loss in realized_pnl, not silently vanish."""
    book = make_book(initial_cash=100_000.0, initial_inventory_kg=0.0)
    book.pay_for_supply_order(kg=150.0, unit_cost=320.0)  # pay for 150kg
    # Only 60kg actually arrives (a partial/failed delivery); 90kg is lost
    book.receive_delivery(kg=60.0, unit_cost=320.0)
    book.record_lost_delivery_cost(90.0 * 320.0)

    assert book.realized_pnl() == pytest.approx(-90.0 * 320.0)
    assert book.inventory_kg == pytest.approx(60.0)


def test_lost_delivery_cost_rejects_negative_value():
    book = make_book()
    with pytest.raises(ValueError):
        book.record_lost_delivery_cost(-10.0)


def test_mark_to_market_pnl_and_terminal_wealth_agree_when_no_deliveries_are_lost():
    """Sanity check: absent any lost-delivery cost, mark_to_market_pnl and
    terminal_wealth should differ only by the (constant) initial capital --
    i.e. the lost-delivery-cost fix doesn't perturb the ordinary case."""
    book = make_book(initial_cash=50_000.0, initial_inventory_kg=0.0)
    book.pay_for_supply_order(kg=100.0, unit_cost=300.0)
    book.receive_delivery(kg=100.0, unit_cost=300.0)  # delivered in full, nothing lost
    book.record_sale(kg=40.0, price=340.0)

    price = 350.0
    mtm = book.mark_to_market_pnl(price)
    tw = book.terminal_wealth(price)
    initial_capital = 50_000.0  # no inventory value counted at t=0 in this project's convention
    assert tw - mtm == pytest.approx(initial_capital)
