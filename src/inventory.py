"""
inventory.py
============

Phase 3 deliverable: separating "inventory" into the five tranches the
roadmap requires, instead of the single `physical_kg` number Phase 1/2 used.

THE FIVE TRANCHES
-------------------
- **Physical Inventory** -- gallium currently sitting in storage, ready to
  sell right now.
- **Committed Inventory** -- gallium already promised to a customer (a
  backorder accepted against future supply) but not yet actually delivered
  to them. Register Section 3, "Committed-inventory treatment": subtracted
  from physical inventory before computing "available" inventory, so it is
  never double-counted as freely quotable stock.
- **In-Transit Inventory** -- gallium that has been ordered and paid for but
  has not yet arrived (tracked by src/supply_chain.py, not this module --
  see `SupplyChain.in_transit_kg()`).
- **Expected Inventory** -- the probability-weighted future contribution of
  in-transit shipments (also tracked by supply_chain.py --
  `SupplyChain.expected_kg()`). Register Section 3, "Expected-inventory
  discounting": NOT treated as equivalent to physical stock.
- **Available Inventory** -- register Section 3's own proposed definition:
  physical inventory minus customer commitments minus operational safety
  stock. This is the number a policy should actually treat as "what I can
  freely sell or use as a buffer," not raw physical inventory.

WHY COMMITTED INVENTORY IS TRACKED SEPARATELY FROM PHYSICAL
------------------------------------------------------------------
If a dealer accepts a backorder (promises 50 kg to a customer against an
incoming shipment) without recording that commitment somewhere, the
dealer's remaining physical stock LOOKS free to sell again to someone else
-- a double-count that would let the simulation oversell inventory that
doesn't actually exist yet. Committed inventory exists specifically to
prevent that: `available_kg()` subtracts it before anything is allowed to
be treated as free.

WHY AVAILABLE INVENTORY SUBTRACTS SAFETY STOCK TOO, NOT JUST COMMITMENTS
------------------------------------------------------------------------------
A dealer that only tracks "physical minus committed" would treat every last
kilogram of on-hand stock as fair game to sell, right up until the shelf is
literally empty. Real dealers hold a buffer specifically so that ordinary
demand variability doesn't cause a stockout while a new shipment is still in
transit. Subtracting `safety_stock_kg` in `available_kg()` makes that buffer
economically real inside the simulation, rather than just a threshold that
happens to trigger a restock order (which is all Phase 1/2's
`restock_threshold_kg` was).

WHY available_kg() IS ALLOWED TO GO NEGATIVE
------------------------------------------------
A negative available_kg means the dealer has already committed and/or
depleted stock below its own safety buffer -- a real, meaningful signal of
overextension that later phases (5, 7, 9) will want to observe and react to
(e.g. via the scarcity premium). Clipping it to zero would hide exactly the
information a scarcity-aware policy needs.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- `safety_stock_kg` is fixed for the life of an InventoryTranches instance,
  set relative to a single aggregate demand rate (Phase 1/2's world, before
  Phase 4's sectors exist) -- register Section 3, "Safety stock level":
  "not derived from a real dealer's policy (none public)."
- Commitments are tracked only as a running total (`committed_kg`), not as
  individually-priced, individually-tracked backorder records -- that
  bookkeeping (which specific order, at what locked-in price, is owed)
  lives in `src/simulation.py`'s backorder queue in Phase 3's simulation
  loop, not in this module. This module only enforces the tranche
  ARITHMETIC; it does not decide who gets paid what.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Phase 1/2's single `physical_kg` number returns, and nothing prevents the
simulation from double-counting committed-but-undelivered stock as freely
sellable inventory -- exactly the conflation the roadmap's mastery
checkpoint (expected vs. physical inventory) is designed to catch.
"""

from dataclasses import dataclass


class InventoryTranches:
    """Physical / Committed / (In-Transit and Expected live in supply_chain.py) / Available."""

    def __init__(self, physical_kg: float, safety_stock_kg: float):
        self.physical_kg = float(physical_kg)
        self.committed_kg = 0.0
        self.safety_stock_kg = float(safety_stock_kg)

    def available_kg(self) -> float:
        """Register Section 3's own proposed definition: physical minus
        customer commitments minus operational safety stock. May be
        negative -- see module docstring."""
        return self.physical_kg - self.committed_kg - self.safety_stock_kg

    def reserve_commitment(self, kg: float) -> None:
        """Promise `kg` to a customer without necessarily having (or without
        yet delivering) the physical stock for it -- e.g. an order accepted
        against an incoming shipment."""
        if kg < 0:
            raise ValueError("commitment quantity must be non-negative")
        self.committed_kg += kg

    def fulfill_commitment(self, kg: float) -> None:
        """A previously committed amount is now actually being delivered to
        the customer: physical stock is consumed and the commitment is
        discharged by the same amount."""
        if kg < 0:
            raise ValueError("fulfillment quantity must be non-negative")
        kg = min(kg, self.committed_kg)  # cannot fulfill more than is owed
        self.committed_kg -= kg
        self.physical_kg = max(0.0, self.physical_kg - kg)

    def consume_physical(self, kg: float) -> None:
        """An ordinary, uncommitted sale: physical stock leaves immediately,
        with no corresponding commitment ever having been recorded."""
        if kg < 0:
            raise ValueError("consumption quantity must be non-negative")
        self.physical_kg = max(0.0, self.physical_kg - kg)

    def receive_delivery(self, kg: float) -> None:
        """A shipment has arrived: physical stock increases. Does not, by
        itself, resolve any pending commitments -- the caller decides how
        much of a delivery goes to satisfying backorders vs. free stock
        (see src/simulation.py's Phase 3 delivery-processing logic)."""
        if kg < 0:
            raise ValueError("delivered quantity must be non-negative")
        self.physical_kg += kg
