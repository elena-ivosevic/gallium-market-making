import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
from src.demand import PoissonOrderFlow, DemandParams, CustomerOrder


def test_order_sizes_are_positive():
    flow = PoissonOrderFlow(DemandParams(arrival_rate_per_year=5000.0), seed=1)
    orders = flow.generate_orders(mid_price=350.0)
    assert all(o.size_kg > 0 for o in orders)


def test_higher_arrival_rate_produces_more_orders_on_average():
    low = DemandParams(arrival_rate_per_year=50.0)
    high = DemandParams(arrival_rate_per_year=2000.0)

    low_counts, high_counts = [], []
    for seed in range(20):
        low_counts.append(len(PoissonOrderFlow(low, seed=seed).generate_orders(350.0)))
        high_counts.append(len(PoissonOrderFlow(high, seed=seed).generate_orders(350.0)))

    assert np.mean(high_counts) > np.mean(low_counts)


def test_order_fills_when_ask_at_or_below_willingness_to_pay():
    order = CustomerOrder(size_kg=10.0, willingness_to_pay=400.0)
    filled_order = PoissonOrderFlow.match_order(order, dealer_ask_price=390.0)
    assert filled_order.filled is True
    assert filled_order.fill_price == 390.0


def test_order_rejected_when_ask_above_willingness_to_pay():
    order = CustomerOrder(size_kg=10.0, willingness_to_pay=400.0)
    rejected_order = PoissonOrderFlow.match_order(order, dealer_ask_price=410.0)
    assert rejected_order.filled is False
    assert rejected_order.fill_price == 0.0


def test_order_exactly_at_willingness_to_pay_fills():
    """Edge case: ask == WTP should fill (dealer quote is <=, not strictly <)."""
    order = CustomerOrder(size_kg=5.0, willingness_to_pay=350.0)
    filled_order = PoissonOrderFlow.match_order(order, dealer_ask_price=350.0)
    assert filled_order.filled is True
