import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.accounting import DealerBook, AccountingParams


def make_book(**overrides):
    params = AccountingParams(**overrides) if overrides else AccountingParams()
    return DealerBook(params)


def test_initial_state():
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=100.0)
    assert book.cash == 10_000.0
    assert book.inventory_kg == 100.0
    assert book.realized_pnl() == 0.0


def test_sale_updates_cash_and_inventory():
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=100.0)
    ok = book.record_sale(kg=20.0, price=400.0)
    assert ok is True
    assert book.inventory_kg == 80.0
    assert book.cash == 10_000.0 + 20.0 * 400.0
    assert book.cumulative_sales_kg == 20.0
    assert book.cumulative_revenue == 20.0 * 400.0


def test_sale_rejected_if_insufficient_inventory():
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=5.0)
    ok = book.record_sale(kg=20.0, price=400.0)
    assert ok is False
    assert book.inventory_kg == 5.0  # unchanged
    assert book.failed_sales == 1


def test_restock_updates_cash_inventory_and_cost_basis():
    # markup_frac is now an explicit call argument (owned by the policy layer,
    # per register Section 6 "Fixed bid spread"), not an AccountingParams field.
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=0.0)
    cost = book.restock(kg=50.0, spot_price=300.0, markup_frac=0.10)
    expected_unit_cost = 300.0 * 1.10
    assert abs(cost - 50.0 * expected_unit_cost) < 1e-6
    assert book.inventory_kg == 50.0
    assert abs(book.avg_cost_basis - expected_unit_cost) < 1e-6
    assert book.cash == 10_000.0 - cost


def test_auto_restock_triggers_below_threshold_and_not_above():
    book = make_book(initial_inventory_kg=200.0, restock_threshold_kg=50.0,
                      restock_amount_kg=100.0)
    # well above threshold: no restock
    spent = book.maybe_auto_restock(spot_price=300.0, markup_frac=0.03)
    assert spent == 0.0
    assert book.restock_events == 0

    # force inventory below threshold via a sale, then check restock fires
    book.record_sale(kg=160.0, price=300.0)  # inventory now 40, below 50 threshold
    spent = book.maybe_auto_restock(spot_price=300.0, markup_frac=0.03)
    assert spent > 0.0
    assert book.restock_events == 1
    assert book.inventory_kg == 40.0 + 100.0


def test_realized_pnl_reflects_markup_cost_via_cogs():
    """Buy at a markup, then sell at the same spot price the goods were bought
    at (before markup) -- realized P&L should be negative because the average
    cost basis includes the replacement markup."""
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=0.0)
    book.restock(kg=100.0, spot_price=300.0, markup_frac=0.10)  # cost basis = 330
    book.record_sale(kg=100.0, price=300.0)   # sold at pre-markup spot price
    assert book.realized_pnl() < 0.0


def test_mark_to_market_pnl_includes_unrealized_inventory_gain():
    book = make_book(initial_cash=10_000.0, initial_inventory_kg=0.0)
    book.restock(kg=100.0, spot_price=300.0, markup_frac=0.0)  # cost basis = 300, no markup
    # price rises to 400 without any sale: mark-to-market should show a gain
    mtm = book.mark_to_market_pnl(current_price=400.0)
    assert mtm == 100.0 * (400.0 - 300.0)


def test_terminal_wealth_is_cash_plus_inventory_value():
    book = make_book(initial_cash=5_000.0, initial_inventory_kg=10.0)
    tw = book.terminal_wealth(current_price=350.0)
    assert tw == 5_000.0 + 10.0 * 350.0


def test_snapshot_records_expected_fields():
    book = make_book()
    row = book.snapshot(t=0, price=350.0)
    expected_keys = {
        "t", "price", "cash", "inventory_kg", "avg_cost_basis",
        "cumulative_sales_kg", "cumulative_purchases_kg", "cumulative_revenue",
        "cumulative_replacement_cost", "realized_pnl", "mark_to_market_pnl",
        "terminal_wealth", "restock_events", "failed_sales",
    }
    assert expected_keys.issubset(row.keys())
    assert len(book.history) == 1
