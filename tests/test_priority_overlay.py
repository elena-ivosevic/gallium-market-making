import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.policies.priority_overlay import PriorityOverlay, PriorityOverlayParams
from src.demand import CustomerOrder


def make_orders():
    return [
        CustomerOrder(size_kg=10.0, willingness_to_pay=400.0, military_linked=False),
        CustomerOrder(size_kg=15.0, willingness_to_pay=400.0, military_linked=True),
        CustomerOrder(size_kg=20.0, willingness_to_pay=400.0, military_linked=False),
    ]


def test_p_must_be_in_unit_interval():
    with pytest.raises(ValueError):
        PriorityOverlayParams(p=1.5)
    with pytest.raises(ValueError):
        PriorityOverlayParams(p=-0.1)


def test_p_zero_never_reorders():
    overlay = PriorityOverlay(PriorityOverlayParams(p=0.0), seed=1)
    orders = make_orders()
    result = overlay.order_sequence(orders)
    assert result == orders
    assert overlay.contested_days == 1  # contention is still counted for diagnostics
    assert overlay.days_military_prioritized == 0  # but never acted on at p=0


def test_single_order_never_contested():
    overlay = PriorityOverlay(PriorityOverlayParams(p=1.0), seed=1)
    orders = [CustomerOrder(size_kg=10.0, willingness_to_pay=400.0, military_linked=True)]
    result = overlay.order_sequence(orders)
    assert result == orders
    assert overlay.contested_days == 0


def test_single_channel_day_never_contested():
    """All civilian, or all military -- nothing to contest."""
    overlay = PriorityOverlay(PriorityOverlayParams(p=1.0), seed=1)
    all_civilian = [
        CustomerOrder(size_kg=10.0, willingness_to_pay=400.0, military_linked=False),
        CustomerOrder(size_kg=15.0, willingness_to_pay=400.0, military_linked=False),
    ]
    result = overlay.order_sequence(all_civilian)
    assert result == all_civilian
    assert overlay.contested_days == 0


def test_p_one_always_prioritizes_military_on_contested_days():
    overlay = PriorityOverlay(PriorityOverlayParams(p=1.0), seed=1)
    orders = make_orders()
    result = overlay.order_sequence(orders)
    assert overlay.contested_days == 1
    assert overlay.days_military_prioritized == 1
    # All military orders should precede all civilian orders
    military_flags = [o.military_linked for o in result]
    first_civilian_idx = military_flags.index(False)
    assert all(military_flags[:first_civilian_idx])


def test_within_channel_relative_order_is_preserved():
    overlay = PriorityOverlay(PriorityOverlayParams(p=1.0), seed=1)
    orders = [
        CustomerOrder(size_kg=1.0, willingness_to_pay=400.0, military_linked=True),
        CustomerOrder(size_kg=2.0, willingness_to_pay=400.0, military_linked=False),
        CustomerOrder(size_kg=3.0, willingness_to_pay=400.0, military_linked=True),
        CustomerOrder(size_kg=4.0, willingness_to_pay=400.0, military_linked=False),
    ]
    result = overlay.order_sequence(orders)
    military_sizes = [o.size_kg for o in result if o.military_linked]
    civilian_sizes = [o.size_kg for o in result if not o.military_linked]
    assert military_sizes == [1.0, 3.0]  # original relative order preserved
    assert civilian_sizes == [2.0, 4.0]


def test_intermediate_p_prioritizes_military_only_probabilistically():
    overlay = PriorityOverlay(PriorityOverlayParams(p=0.5), seed=2)
    prioritized_count = 0
    n_trials = 200
    for _ in range(n_trials):
        result = overlay.order_sequence(make_orders())
        if result[0].military_linked:
            prioritized_count += 1
    fraction = prioritized_count / n_trials
    assert 0.3 < fraction < 0.7  # roughly 50%, allowing for sampling noise


def test_deterministic_given_seed():
    overlay_a = PriorityOverlay(PriorityOverlayParams(p=0.5), seed=42)
    overlay_b = PriorityOverlay(PriorityOverlayParams(p=0.5), seed=42)
    results_a = [overlay_a.order_sequence(make_orders())[0].military_linked for _ in range(20)]
    results_b = [overlay_b.order_sequence(make_orders())[0].military_linked for _ in range(20)]
    assert results_a == results_b
