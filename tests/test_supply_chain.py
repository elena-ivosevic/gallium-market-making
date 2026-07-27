import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.supply_chain import SupplyChain, SupplyChainParams


def make_chain(**overrides):
    params = SupplyChainParams(**overrides) if overrides else SupplyChainParams()
    return SupplyChain(params, seed=1)


def test_place_order_adds_to_pending_and_counts():
    chain = make_chain()
    shipment = chain.place_order(100.0)
    assert len(chain.pending) == 1
    assert chain.total_shipments_placed == 1
    assert chain.total_emergency_orders == 0
    assert shipment.kg_ordered == 100.0
    assert shipment.emergency is False


def test_emergency_order_uses_shorter_lead_time():
    chain = make_chain(lead_time_days=14, emergency_lead_time_days=3)
    normal = chain.place_order(50.0, emergency=False)
    emergency = chain.place_order(50.0, emergency=True)
    assert normal.days_remaining == 14
    assert emergency.days_remaining == 3
    assert chain.total_emergency_orders == 1


def test_place_order_rejects_non_positive_quantity():
    chain = make_chain()
    with pytest.raises(ValueError):
        chain.place_order(0.0)
    with pytest.raises(ValueError):
        chain.place_order(-5.0)


def test_shipment_not_resolved_before_lead_time_elapses():
    chain = make_chain(lead_time_days=5)
    chain.place_order(100.0)
    for _ in range(4):
        resolved = chain.advance_day()
        assert resolved == []
    assert len(chain.pending) == 1


def test_shipment_resolves_exactly_at_lead_time():
    chain = make_chain(lead_time_days=3)
    chain.place_order(100.0)
    chain.advance_day()
    chain.advance_day()
    resolved = chain.advance_day()
    assert len(resolved) == 1
    assert resolved[0].resolved is True
    assert len(chain.pending) == 0


def test_high_reliability_delivers_in_full_most_of_the_time():
    """Statistical check: with reliability=0.99, the vast majority of many
    independent 1-day shipments should deliver in full."""
    chain = make_chain(lead_time_days=1, reliability=0.99)
    full_deliveries = 0
    n = 300
    for _ in range(n):
        chain.place_order(100.0)
    resolved = chain.advance_day()
    for s in resolved:
        if s.delivered_kg == pytest.approx(100.0):
            full_deliveries += 1
    assert full_deliveries / n > 0.9


def test_low_reliability_produces_more_failed_deliveries():
    chain_low = make_chain(lead_time_days=1, reliability=0.2)
    chain_high = make_chain(lead_time_days=1, reliability=0.95)
    for _ in range(200):
        chain_low.place_order(100.0)
        chain_high.place_order(100.0)
    chain_low.advance_day()
    chain_high.advance_day()
    assert chain_low.total_failed_deliveries > chain_high.total_failed_deliveries


def test_failed_delivery_delivers_partial_fraction_within_configured_bounds():
    chain = make_chain(lead_time_days=1, reliability=0.0,  # force every delivery to "fail"
                         partial_failure_min_frac=0.1, partial_failure_max_frac=0.4)
    chain.place_order(200.0)
    resolved = chain.advance_day()
    assert len(resolved) == 1
    delivered_frac = resolved[0].delivered_kg / 200.0
    assert 0.1 <= delivered_frac <= 0.4
    assert chain.total_failed_deliveries == 1
    assert chain.total_kg_lost_to_failure == pytest.approx(200.0 - resolved[0].delivered_kg)


def test_in_transit_kg_sums_full_ordered_amount_for_all_pending_shipments():
    chain = make_chain(lead_time_days=10)
    chain.place_order(100.0)
    chain.place_order(50.0)
    assert chain.in_transit_kg() == pytest.approx(150.0)


def test_expected_kg_uses_ex_ante_reliability_not_realized_outcome():
    """The mastery-checkpoint arithmetic: a 200kg shipment at 50% reliability
    contributes 100kg to expected inventory, regardless of what it actually
    delivers once resolved."""
    chain = make_chain(lead_time_days=10, reliability=0.5)
    chain.place_order(200.0)
    assert chain.expected_kg() == pytest.approx(100.0)


def test_expected_kg_sums_across_multiple_shipments_with_different_reliabilities():
    chain = make_chain(lead_time_days=10, reliability=0.5)
    chain.place_order(200.0)  # contributes 100 at reliability 0.5
    shipment2 = chain.place_order(100.0)
    shipment2.reliability = 0.8  # manually override for this shipment specifically
    assert chain.expected_kg() == pytest.approx(200.0 * 0.5 + 100.0 * 0.8)


def test_replacement_markup_equals_base_when_available_at_or_above_safety_stock():
    chain = make_chain(replacement_cost_base_markup=0.03, replacement_cost_curvature=2.0)
    markup = chain.replacement_markup_frac(available_kg=100.0, safety_stock_kg=60.0)
    assert markup == pytest.approx(0.03)


def test_replacement_markup_rises_convexly_as_available_inventory_falls():
    chain = make_chain(replacement_cost_base_markup=0.03, replacement_cost_curvature=2.0)
    m_safe = chain.replacement_markup_frac(available_kg=60.0, safety_stock_kg=60.0)
    m_half_deficit = chain.replacement_markup_frac(available_kg=30.0, safety_stock_kg=60.0)
    m_full_deficit = chain.replacement_markup_frac(available_kg=0.0, safety_stock_kg=60.0)

    assert m_safe < m_half_deficit < m_full_deficit
    # Convexity check: the SECOND half of the shortfall should add MORE
    # markup than the first half (rising marginal cost), not the same amount.
    first_half_increase = m_half_deficit - m_safe
    second_half_increase = m_full_deficit - m_half_deficit
    assert second_half_increase > first_half_increase


def test_replacement_markup_caps_out_for_deeply_negative_available_kg():
    """The shortfall ratio is capped at 1.0 (available_kg <= 0), so markup
    should stop rising past that point rather than growing without bound."""
    chain = make_chain(replacement_cost_base_markup=0.03, replacement_cost_curvature=2.0)
    m_at_zero = chain.replacement_markup_frac(available_kg=0.0, safety_stock_kg=60.0)
    m_negative = chain.replacement_markup_frac(available_kg=-60.0, safety_stock_kg=60.0)
    m_very_negative = chain.replacement_markup_frac(available_kg=-1000.0, safety_stock_kg=60.0)
    assert m_at_zero == pytest.approx(0.03 + 2.0)  # base + full curvature, ratio capped at 1.0
    assert m_negative == pytest.approx(m_at_zero)
    assert m_very_negative == pytest.approx(m_at_zero)
