import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from src.inventory import InventoryTranches


def test_initial_state():
    tranches = InventoryTranches(physical_kg=200.0, safety_stock_kg=60.0)
    assert tranches.physical_kg == 200.0
    assert tranches.committed_kg == 0.0
    assert tranches.available_kg() == pytest.approx(140.0)


def test_available_kg_subtracts_both_committed_and_safety_stock():
    tranches = InventoryTranches(physical_kg=200.0, safety_stock_kg=60.0)
    tranches.reserve_commitment(50.0)
    assert tranches.available_kg() == pytest.approx(200.0 - 50.0 - 60.0)


def test_available_kg_can_go_negative():
    tranches = InventoryTranches(physical_kg=50.0, safety_stock_kg=60.0)
    tranches.reserve_commitment(20.0)
    assert tranches.available_kg() == pytest.approx(50.0 - 20.0 - 60.0)
    assert tranches.available_kg() < 0


def test_reserve_commitment_rejects_negative_quantity():
    tranches = InventoryTranches(physical_kg=100.0, safety_stock_kg=60.0)
    with pytest.raises(ValueError):
        tranches.reserve_commitment(-10.0)


def test_fulfill_commitment_reduces_both_committed_and_physical():
    tranches = InventoryTranches(physical_kg=200.0, safety_stock_kg=60.0)
    tranches.reserve_commitment(80.0)
    tranches.fulfill_commitment(50.0)
    assert tranches.committed_kg == pytest.approx(30.0)
    assert tranches.physical_kg == pytest.approx(150.0)


def test_fulfill_commitment_cannot_exceed_outstanding_commitment():
    """Fulfilling more than is actually owed should cap at the outstanding
    commitment, not go negative or over-consume physical stock."""
    tranches = InventoryTranches(physical_kg=200.0, safety_stock_kg=60.0)
    tranches.reserve_commitment(30.0)
    tranches.fulfill_commitment(100.0)  # ask for more than the 30kg owed
    assert tranches.committed_kg == pytest.approx(0.0)
    assert tranches.physical_kg == pytest.approx(170.0)  # only 30kg actually consumed


def test_consume_physical_does_not_touch_committed():
    tranches = InventoryTranches(physical_kg=200.0, safety_stock_kg=60.0)
    tranches.reserve_commitment(40.0)
    tranches.consume_physical(30.0)
    assert tranches.physical_kg == pytest.approx(170.0)
    assert tranches.committed_kg == pytest.approx(40.0)  # unaffected


def test_consume_physical_floors_at_zero():
    tranches = InventoryTranches(physical_kg=10.0, safety_stock_kg=60.0)
    tranches.consume_physical(50.0)
    assert tranches.physical_kg == 0.0


def test_receive_delivery_increases_physical_only():
    tranches = InventoryTranches(physical_kg=50.0, safety_stock_kg=60.0)
    tranches.reserve_commitment(20.0)
    tranches.receive_delivery(100.0)
    assert tranches.physical_kg == pytest.approx(150.0)
    assert tranches.committed_kg == pytest.approx(20.0)  # unaffected by receiving stock


def test_receive_delivery_rejects_negative_quantity():
    tranches = InventoryTranches(physical_kg=50.0, safety_stock_kg=60.0)
    with pytest.raises(ValueError):
        tranches.receive_delivery(-5.0)


def test_expected_vs_physical_worked_example_from_mastery_checkpoint():
    """
    The Phase 3 mastery-checkpoint numerical example: 200kg shipment at 50%
    arrival probability contributes 100kg of EXPECTED inventory (tracked in
    supply_chain.py), which is fundamentally different from 100kg already
    sitting in the warehouse as PHYSICAL inventory (tracked here) --
    physical inventory is immediately available_kg-countable; expected
    inventory, by construction, is not (see InventoryTranches.available_kg,
    which only ever reads physical_kg, never a supply chain's expected_kg).
    """
    tranches_with_100kg_physical = InventoryTranches(physical_kg=100.0, safety_stock_kg=60.0)
    tranches_with_0kg_physical = InventoryTranches(physical_kg=0.0, safety_stock_kg=60.0)

    # Even though "200kg at 50%" and "100kg physical" both nominally
    # represent "100kg," only the physical case contributes to available_kg.
    assert tranches_with_100kg_physical.available_kg() == pytest.approx(40.0)
    assert tranches_with_0kg_physical.available_kg() == pytest.approx(-60.0)
    assert tranches_with_100kg_physical.available_kg() != tranches_with_0kg_physical.available_kg()
