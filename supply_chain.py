"""
supply_chain.py
================

Phase 3 deliverable: Supply-Chain Mechanics -- shipment lead times, delivery
delays, partial deliveries, failed deliveries, emergency replacement
purchases, supplier reliability, and a nonlinear (convex) replacement-cost
function. This is the module that Phase 1's `accounting.py` explicitly
flagged as scaffolding to be replaced ("Restock is instant with no lead time
or failure probability -- this is scaffolding").

WHAT THIS MODULE DOES
----------------------
A `SupplyChain` tracks a queue of pending `Shipment`s. Each shipment has a
lead time (days until it's due to arrive) and a reliability (probability of
arriving in full). Every simulated day:
  1. Every pending shipment's lead time counts down by one.
  2. Any shipment reaching zero days remaining is RESOLVED: a Bernoulli draw
     against its reliability decides whether it arrives in full, or partially
     (a random fraction of the ordered amount, representing damage, customs
     delay, or a partial-fill supplier decision) -- see "Partial vs. failed
     deliveries" below.
  3. The caller (src/simulation.py in Phase 3 mode) is responsible for
     turning resolved deliveries into physical inventory (src/inventory.py)
     and for deciding when to place new orders.

WHY LEAD TIMES AND RELIABILITY, NOT INSTANT RESTOCK
------------------------------------------------------
A gallium dealer cannot conjure inventory the moment cash is spent -- there
is a real delay between placing an order and receiving usable stock, and a
real chance the shipment doesn't arrive as ordered (register Section 2,
"Normal-regime shipment reliability": 95%; Section 3, "Shipment lead time
(Normal)"). Modeling this is the entire point of Phase 3: it creates the gap
between "gallium that has been paid for" and "gallium that is actually
available to sell," which is what makes Expected Inventory a genuinely
different quantity from Physical Inventory (see the module docstring in
src/inventory.py and this project's Phase 3 mastery checkpoint).

PARTIAL VS. FAILED DELIVERIES
--------------------------------
The roadmap distinguishes "partial deliveries" from "failed deliveries" as
separate mechanics. This module treats them as two outcomes of the SAME
resolution event rather than two independent processes: on the reliability
draw's failure branch, the delivered fraction is drawn from
Uniform(partial_failure_min_frac, partial_failure_max_frac) rather than
being hard-coded to zero. With the default bounds (0.0 to 0.5), a "failed"
shipment can still deliver anywhere from nothing up to half the ordered
amount -- a full write-off is one possible outcome of a failure, not the
only one. This is a judgment call (no public gallium logistics-failure data
exists to fit a real distribution), logged in
docs/assumptions_register.md, Section 9.

WHY EMERGENCY ORDERS HAVE THEIR OWN (SHORTER, NOT ZERO) LEAD TIME
----------------------------------------------------------------------
An emergency replacement purchase is faster than a normal order (expedited
freight, premium sourcing) but still not instantaneous -- treating it as
Phase 1's instant restock would just be Phase 1's shortcut wearing an
"emergency" label. `emergency_lead_time_days` is deliberately shorter than
`lead_time_days` but still greater than zero, and emergency orders carry an
extra cost multiplier (paid on top of the nonlinear replacement-cost markup)
to reflect that expediting is itself costly.

NONLINEAR REPLACEMENT COST
------------------------------
`replacement_markup_frac(available_kg)` implements the register's
"Replacement-cost curvature parameter" row directly: the markup a dealer
pays to place a NEW order rises convexly (as the square of the shortfall
ratio) as available inventory falls toward and below the safety-stock level.
This is deliberately continuous with Phase 1/2's flat `restock_markup_frac`
(the two coincide when available_kg >= safety_stock_kg, i.e., shortfall = 0)
rather than a wholly separate mechanism -- Phase 3 sharpens Phase 1/2's flat
assumption, it doesn't discard it.

WHAT THIS MODULE DELIBERATELY DOES NOT DO (a real, flagged gap)
--------------------------------------------------------------------
The roadmap's Phase 3 "Add Supply-Chain Mechanics" list also calls for
"channel-dependent shipment reliability" -- separate civilian and
military-linked reliability tracks. THIS IS NOT IMPLEMENTED HERE. Every
parameter in this project is required to have a prior row in
docs/assumptions_register.md before it appears in code (that rule was
violated once already, in Phase 1, and corrected -- see the register's
Section 7 "Known deviations"). The current register has no military-linked
demand or channel-reliability rows at all (Sections 1-6, as delivered by
Phase 0, are civilian/aggregate-only). Building a military/civilian
reliability split now would repeat exactly the mistake Phase 1 made and then
fixed. This is logged as an explicit, deferred gap in
docs/assumptions_register.md, Section 9, to be resolved with a proper
register addendum before or during Phase 4 (which needs
`military_linked_share` and sector structure anyway) -- not smuggled into
Phase 3 without documentation.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Delivery resolution is all-or-mostly-at-once at the end of the lead time,
  not progressive (no shipment arrives "10% today, 20% tomorrow").
- `reliability` is a single Normal-regime constant reused from the register's
  existing "Normal-regime shipment reliability" row; regime-dependent
  reliability (Delayed/Severe/Recovery) is explicitly Phase 4's job -- this
  module never varies reliability over time on its own.
- The failure-branch delivered-fraction distribution (Uniform over a fixed
  range) is a judgment call, not fitted to any real failure-rate data.
- No channel-dependent (military/civilian) reliability -- see above.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Without it, Phase 3's whole point disappears: there would be no gap between
"ordered" and "arrived" inventory, no meaningful Expected vs. Physical
inventory distinction, and restocking would fall back to Phase 1's
instant, zero-failure stub -- exactly what Phase 3 exists to replace.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class SupplyChainParams:
    lead_time_days: int = 14                  # register §3 "Shipment lead time (Normal)" --
                                                # judgment call, "days to low weeks"
    reliability: float = 0.95                  # register §2 "Normal-regime shipment
                                                # reliability" -- reused here since Phase 4's
                                                # regime switch does not exist yet
    partial_failure_min_frac: float = 0.0      # judgment call: on failure, delivered
    partial_failure_max_frac: float = 0.5      # fraction ~ Uniform(min, max); no fitted
                                                # failure-severity data exists
    emergency_lead_time_days: int = 3          # judgment call: faster than normal, not instant
    emergency_cost_multiplier: float = 1.5     # judgment call: extra cost for expediting,
                                                # applied on top of replacement_markup_frac
    replacement_cost_base_markup: float = 0.03  # matches Phase 1/2's restock_markup_frac --
                                                # register §6 "Fixed bid spread" (reinterpreted)
    replacement_cost_curvature: float = 2.0     # register §3 "Replacement-cost curvature
                                                # parameter" -- judgment call, convexity
                                                # magnitude


@dataclass
class Shipment:
    shipment_id: int
    kg_ordered: float
    days_remaining: int
    reliability: float
    emergency: bool = False
    resolved: bool = False
    delivered_kg: float = 0.0
    unit_cost_locked: float = 0.0  # set by the caller (src/simulation.py) right after
                                    # place_order -- SupplyChain itself has no notion of
                                    # cost; this is pure bookkeeping metadata so
                                    # accounting.py's receive_delivery() can use the cost
                                    # that was actually paid at ORDER time, not whatever
                                    # spot happens to be when the shipment arrives


class SupplyChain:
    """Tracks pending shipments; resolves deliveries day by day."""

    def __init__(self, params: SupplyChainParams, seed: int | None = None):
        self.p = params
        self.rng = np.random.default_rng(seed)
        self.pending: list[Shipment] = []
        self._next_id = 1
        self.total_shipments_placed = 0
        self.total_emergency_orders = 0
        self.total_failed_deliveries = 0    # deliveries that arrived below 100% of ordered
        self.total_kg_lost_to_failure = 0.0

    def place_order(self, kg: float, emergency: bool = False) -> Shipment:
        if kg <= 0:
            raise ValueError("order quantity must be positive")
        lead_time = self.p.emergency_lead_time_days if emergency else self.p.lead_time_days
        shipment = Shipment(
            shipment_id=self._next_id,
            kg_ordered=kg,
            days_remaining=lead_time,
            reliability=self.p.reliability,
            emergency=emergency,
        )
        self._next_id += 1
        self.pending.append(shipment)
        self.total_shipments_placed += 1
        if emergency:
            self.total_emergency_orders += 1
        return shipment

    def advance_day(self) -> list[Shipment]:
        """
        Decrement every pending shipment's lead time by one day; resolve
        (deliver) any shipment that reaches zero. Returns the list of
        shipments resolved on THIS call (each has `delivered_kg` set).
        """
        resolved_now = []
        still_pending = []
        for s in self.pending:
            s.days_remaining -= 1
            if s.days_remaining <= 0:
                success = self.rng.random() < s.reliability
                if success:
                    s.delivered_kg = s.kg_ordered
                else:
                    frac = self.rng.uniform(
                        self.p.partial_failure_min_frac, self.p.partial_failure_max_frac
                    )
                    s.delivered_kg = s.kg_ordered * frac
                    self.total_failed_deliveries += 1
                    self.total_kg_lost_to_failure += s.kg_ordered - s.delivered_kg
                s.resolved = True
                resolved_now.append(s)
            else:
                still_pending.append(s)
        self.pending = still_pending
        return resolved_now

    def in_transit_kg(self) -> float:
        """
        Register Section 3, "In-Transit Inventory": gallium ordered and
        shipped but not yet arrived. Every pending shipment contributes its
        FULL ordered quantity (none of it counts as arrived until the
        shipment resolves at the end of its lead time -- see module
        docstring, "Limitations").
        """
        return sum(s.kg_ordered for s in self.pending)

    def expected_kg(self) -> float:
        """
        Register Section 3, "Expected Inventory": probability-adjusted
        future supply. Uses each shipment's EX-ANTE reliability (the known
        probability parameter), not the as-yet-unresolved random outcome --
        e.g. a 200 kg shipment at 50% reliability contributes 100 kg here,
        matching the register's own worked example, regardless of what that
        shipment eventually actually delivers.
        """
        return sum(s.kg_ordered * s.reliability for s in self.pending)

    def replacement_markup_frac(self, available_kg: float, safety_stock_kg: float) -> float:
        """
        Register Section 3, "Replacement-cost curvature parameter": the
        markup paid to place a NEW order rises convexly (as the square of
        the shortfall ratio) as available inventory falls toward and below
        safety stock. Coincides with the flat `replacement_cost_base_markup`
        when available_kg >= safety_stock_kg (shortfall = 0).

        The shortfall ratio is CAPPED at 1.0 (i.e., at available_kg <= 0):
        an uncapped version grows without bound for deeply negative
        available_kg (e.g. a heavily over-committed dealer), producing
        markups of many hundred or thousand percent -- not a meaningful
        "scarcity premium" at that point, just a runaway number. Capping
        means the worst-case markup is `base_markup + curvature` (e.g. 3%
        + 200% = 203% at the defaults), which is still a severe, clearly
        "emergency-tier" cost, without being economically meaningless.
        This cap was added after an early Phase 3 integration run produced
        markups over 60,000% and multi-million-dollar simulated losses from
        the uncapped version -- see docs/assumptions_register.md, Section 9.
        """
        if safety_stock_kg <= 0:
            return self.p.replacement_cost_base_markup
        shortfall = max(0.0, safety_stock_kg - available_kg)
        shortfall_ratio = min(1.0, shortfall / safety_stock_kg)
        return self.p.replacement_cost_base_markup + self.p.replacement_cost_curvature * (
            shortfall_ratio ** 2
        )
