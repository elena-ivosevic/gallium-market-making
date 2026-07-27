"""
accounting.py
=============

Phase 1 deliverable: Dealer Accounting + a minimal restock mechanism.
Phase 3 update: physical inventory now lives in an InventoryTranches object
(src/inventory.py) instead of a bare float, and new methods support
supply-chain-driven restocking (src/supply_chain.py) and customer
commitments/backorders -- WITHOUT removing or changing the behavior of any
Phase 1/2 method. Every Phase 1/2 test that exercises this file continues to
pass unchanged; Phase 3 functionality is additive.

WHAT THIS TRACKS
----------------
- cash                  : USD on hand
- inventory_kg          : PROPERTY, now backed by tranches.physical_kg (Phase 3)
                          -- reads/writes behave exactly as the old plain
                          float did, for backward compatibility
- committed_kg          : (Phase 3) gallium promised to customers but not
                          yet delivered -- see src/inventory.py
- cumulative_purchases  : total kg bought from the supply market (restocking)
- cumulative_sales      : total kg sold to customers
- cumulative_revenue    : total USD received from customer sales
- cumulative_replacement_cost : total USD spent restocking inventory
- realized_pnl          : cash-basis P&L (revenue - cost of goods sold - replacement cost)
- mark_to_market_pnl    : realized_pnl + (inventory_kg * current_price) - initial capital
- total_terminal_wealth : cash + inventory_kg * current_price (computed on demand)

WHY A SEPARATE "REALIZED" VS "MARK-TO-MARKET" P&L
----------------------------------------------------
A dealer holding physical inventory has paper gains/losses that are not cash
yet. Conflating the two would let a policy look artificially good (or bad)
just because gallium prices moved, rather than because the dealer traded
well. Keeping both numbers lets later phases separate "the dealer made good
trading decisions" from "the market happened to move in the dealer's favor."

PHASE 1 MINIMAL RESTOCK MECHANISM (UNCHANGED, KEPT FOR BACKWARD COMPATIBILITY)
--------------------------------------------------------------------------------
`restock()` and `maybe_auto_restock()` are UNCHANGED from Phase 1/2: instant,
deterministic, zero-failure-probability restocking. They still work exactly
as before and Phase 1/2 tests still exercise them directly. Phase 3's
`src/simulation.py`, however, no longer CALLS these methods when a
`SupplyChainParams` is supplied -- it uses the new methods below instead
(`pay_for_supply_order`, `receive_delivery`, `reserve_commitment`,
`deliver_against_commitment`). See src/simulation.py and
src/supply_chain.py's module docstrings for why instant restocking was
"scaffolding to be torn out and replaced," and how it now actually is, for
any simulation that opts into supply-chain mode.

PHASE 3 ADDITIONS
--------------------
- `pay_for_supply_order(kg, unit_cost)`: debits cash when a NEW supply-chain
  order is PLACED (the dealer locks in a contract price up front). Does NOT
  touch physical inventory or cost basis -- the kg isn't physically on hand
  yet (it's in-transit; see src/supply_chain.py).
- `receive_delivery(kg, unit_cost)`: called when a shipment actually
  ARRIVES. Increases physical inventory and updates the weighted-average
  cost basis using the cost LOCKED IN at order-placement time, not the spot
  price at delivery time -- consistent with having already paid for it via
  `pay_for_supply_order`.
- `reserve_commitment(kg)` / `deliver_against_commitment(kg, price)`: accept
  a customer backorder against future supply, and later fulfill it (revenue
  recognized at DELIVERY, not at the time the backorder was accepted --
  standard revenue-recognition practice: you can't recognize revenue for
  goods you haven't yet handed over).
- `available_kg()`: register Section 3's proposed definition (physical minus
  committed minus safety stock), delegated to the InventoryTranches object.

WHY REVENUE IS RECOGNIZED AT DELIVERY, NOT AT BACKORDER ACCEPTANCE
------------------------------------------------------------------------
If a dealer counted revenue the moment it promised a customer gallium it
doesn't yet physically have, its books would show profit for goods that
might still fail to arrive (see supply_chain.py's partial/failed delivery
mechanics). Recognizing revenue only when the goods are actually handed
over keeps `realized_pnl()` meaning what it says: profit that has actually
been earned, not profit that has merely been promised.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- `committed_kg` is tracked only as a running total on InventoryTranches;
  which specific customer is owed how much, at what locked-in price, is
  tracked by src/simulation.py's backorder queue (a Phase 3 simulation-loop
  concern), not by this module.
- The Phase 1 restock methods remain fully functional but are effectively
  dead code from Phase 3 onward whenever a SupplyChainParams is supplied --
  kept only for backward compatibility with Phase 1/2 tests and any
  simulation that does not opt into supply-chain mode.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Without accounting, there is no way to score a policy -- P&L, inventory
risk, and terminal wealth all come from here. Without either restocking path
(Phase 1's instant stub or Phase 3's supply-chain-driven orders), every
policy eventually sells out of inventory and the simulation becomes a
trivial "how fast do you sell your starting stock" exercise.
"""

from dataclasses import dataclass, field
import numpy as np

from src.inventory import InventoryTranches


@dataclass
class AccountingParams:
    initial_cash: float = 50_000.0
    initial_inventory_kg: float = 200.0
    restock_threshold_kg: float = 50.0     # Phase 1 stub trigger (register Section 3:
                                            # "Safety stock level" -- judgment call). Kept
                                            # for backward compatibility; Phase 3 simulations
                                            # use safety_stock_kg below instead.
    restock_amount_kg: float = 150.0       # Phase 1 stub restock lot size (judgment call,
                                            # register Section 7)
    safety_stock_kg: float = 60.0          # (Phase 3, new) register Section 3 "Safety stock
                                            # level" -- the buffer subtracted in
                                            # InventoryTranches.available_kg(). Distinct field
                                            # from restock_threshold_kg so Phase 1/2 behavior
                                            # is completely undisturbed by this addition.


class DealerBook:
    """Tracks cash, inventory, and P&L for one dealer/policy over a simulation."""

    def __init__(self, params: AccountingParams):
        self.p = params
        self.cash = float(params.initial_cash)
        self.tranches = InventoryTranches(
            physical_kg=params.initial_inventory_kg,
            safety_stock_kg=params.safety_stock_kg,
        )
        self.cumulative_purchases_kg = 0.0
        self.cumulative_sales_kg = 0.0
        self.cumulative_revenue = 0.0
        self.cumulative_replacement_cost = 0.0
        self.cumulative_cogs = 0.0  # cost of goods sold, at weighted-average cost basis
        self.cumulative_lost_delivery_cost = 0.0  # (Phase 3) cash paid for kg that was
                                            # ordered and paid for but never arrived --
                                            # see record_lost_delivery_cost() below
        self.avg_cost_basis = 0.0   # running weighted-average cost per kg of held inventory
        self.restock_events = 0
        self.failed_sales = 0       # orders rejected due to insufficient inventory
        self.history: list[dict] = []

    # ---- backward-compatible inventory_kg property (Phase 3) --------------

    @property
    def inventory_kg(self) -> float:
        """Physical inventory. Backed by self.tranches.physical_kg since
        Phase 3; reads/writes behave exactly as the old plain float did."""
        return self.tranches.physical_kg

    @inventory_kg.setter
    def inventory_kg(self, value: float) -> None:
        self.tranches.physical_kg = value

    @property
    def committed_kg(self) -> float:
        """(Phase 3) Read-only convenience accessor -- see src/inventory.py."""
        return self.tranches.committed_kg

    def available_kg(self) -> float:
        """(Phase 3) Register Section 3: physical - committed - safety stock."""
        return self.tranches.available_kg()

    # ---- core operations (Phase 1/2, unchanged) ---------------------------

    def record_sale(self, kg: float, price: float) -> bool:
        """
        Sell `kg` of inventory to a customer at `price` USD/kg.
        Returns False (and does nothing) if there isn't enough inventory.
        """
        if kg <= 0:
            return False
        if kg > self.inventory_kg + 1e-9:
            self.failed_sales += 1
            return False

        revenue = kg * price
        cogs = kg * self.avg_cost_basis

        self.cash += revenue
        self.inventory_kg -= kg
        self.cumulative_sales_kg += kg
        self.cumulative_revenue += revenue
        self.cumulative_cogs += cogs
        return True

    def restock(self, kg: float, spot_price: float, markup_frac: float) -> float:
        """
        Buy `kg` of inventory at spot_price * (1 + markup_frac).
        Updates weighted-average cost basis. Returns the total cost paid.

        Phase 1/2 instant-restock stub, UNCHANGED. See module docstring for
        why this remains functional but is not called by Phase 3 simulations.
        """
        if kg <= 0:
            return 0.0
        unit_cost = spot_price * (1.0 + markup_frac)
        total_cost = kg * unit_cost

        # Weighted-average cost basis update
        old_value = self.inventory_kg * self.avg_cost_basis
        new_value = old_value + total_cost
        new_qty = self.inventory_kg + kg
        self.avg_cost_basis = new_value / new_qty if new_qty > 0 else 0.0

        self.cash -= total_cost
        self.inventory_kg = new_qty
        self.cumulative_purchases_kg += kg
        self.cumulative_replacement_cost += total_cost
        self.restock_events += 1
        return total_cost

    def maybe_auto_restock(self, spot_price: float, markup_frac: float) -> float:
        """Apply the Phase 1 minimal restock rule (see module docstring)."""
        if self.inventory_kg <= self.p.restock_threshold_kg:
            return self.restock(self.p.restock_amount_kg, spot_price, markup_frac)
        return 0.0

    # ---- Phase 3 supply-chain-driven operations ---------------------------

    def pay_for_supply_order(self, kg: float, unit_cost: float) -> float:
        """
        Debit cash for a NEW supply-chain order at the moment it is PLACED
        (the dealer locks in a contract price up front). Does NOT touch
        physical inventory or cost basis yet -- the kg is in-transit, not
        physically on hand (see src/supply_chain.py). Returns total cost paid.
        """
        if kg <= 0:
            return 0.0
        total_cost = kg * unit_cost
        self.cash -= total_cost
        self.cumulative_replacement_cost += total_cost
        return total_cost

    def receive_delivery(self, kg: float, unit_cost: float) -> None:
        """
        A shipment has ARRIVED: physical inventory increases, and the
        weighted-average cost basis updates using the cost locked in at
        order-placement time (`unit_cost`), consistent with having already
        paid via `pay_for_supply_order`. Cash is NOT touched here (it was
        already debited at order placement).
        """
        if kg <= 0:
            return
        old_value = self.tranches.physical_kg * self.avg_cost_basis
        new_value = old_value + kg * unit_cost
        new_qty = self.tranches.physical_kg + kg
        self.avg_cost_basis = new_value / new_qty if new_qty > 0 else 0.0
        self.tranches.receive_delivery(kg)
        self.cumulative_purchases_kg += kg

    def reserve_commitment(self, kg: float) -> None:
        """(Phase 3) Accept a customer backorder against future supply --
        see src/inventory.py's InventoryTranches.reserve_commitment."""
        self.tranches.reserve_commitment(kg)

    def deliver_against_commitment(self, kg: float, price: float) -> float:
        """
        (Phase 3) Fulfill a previously-committed (backordered) sale: physical
        inventory MUST already reflect the delivered stock (call
        `receive_delivery` first). Recognizes revenue/COGS like a normal
        sale, at the price LOCKED IN when the backorder was accepted, and
        discharges the commitment. Returns the kg actually delivered against
        the commitment (may be less than requested if physical stock or the
        outstanding commitment itself is smaller).
        """
        kg = min(kg, self.tranches.committed_kg, self.tranches.physical_kg)
        if kg <= 0:
            return 0.0
        revenue = kg * price
        cogs = kg * self.avg_cost_basis
        self.cash += revenue
        self.cumulative_sales_kg += kg
        self.cumulative_revenue += revenue
        self.cumulative_cogs += cogs
        self.tranches.fulfill_commitment(kg)  # decreases both committed_kg and physical_kg
        return kg

    def record_lost_delivery_cost(self, cost: float) -> None:
        """
        (Phase 3) Recognize the sunk cost of kg that was PAID FOR (via
        `pay_for_supply_order`) but never actually arrived, in full or in
        part (a failed/partial delivery -- see src/supply_chain.py). Cash
        was already debited at order-placement time; this method exists
        purely to make that loss VISIBLE in `realized_pnl()`, which would
        otherwise silently miss it -- kg that is paid for but never delivered
        never becomes inventory, so it never flows through cost-of-goods-sold
        at the point of a sale (there is no sale of gallium that doesn't
        exist). Without this, `realized_pnl()` and `mark_to_market_pnl()`
        would UNDERSTATE losses in any scenario with delivery failures, even
        though `terminal_wealth()` (cash + inventory * price) would still
        correctly reflect the loss through reduced cash. This gap was found
        by comparing terminal_wealth against mark_to_market_pnl in a stressed
        (low-reliability) Phase 3 integration run -- see
        docs/assumptions_register.md, Section 9.
        """
        if cost < 0:
            raise ValueError("lost delivery cost must be non-negative")
        self.cumulative_lost_delivery_cost += cost

    # ---- P&L / reporting --------------------------------------------------

    def realized_pnl(self) -> float:
        """Cash-basis P&L: revenue - cost of goods sold - (Phase 3) sunk cost
        of paid-for kg that never arrived. Ordinary replacement cost is
        already reflected through COGS at the point of sale (weighted-average
        cost basis), so it is not subtracted a second time here -- only the
        LOST portion (never delivered, so never eligible to be sold) is
        subtracted directly, since it can never flow through COGS."""
        return self.cumulative_revenue - self.cumulative_cogs - self.cumulative_lost_delivery_cost

    def mark_to_market_pnl(self, current_price: float) -> float:
        """Realized P&L plus unrealized gain/loss on remaining inventory,
        valued at current spot price against its average cost basis."""
        unrealized = self.inventory_kg * (current_price - self.avg_cost_basis)
        return self.realized_pnl() + unrealized

    def terminal_wealth(self, current_price: float) -> float:
        """Total liquidation value: cash on hand + inventory valued at spot."""
        return self.cash + self.inventory_kg * current_price

    def snapshot(self, t: float, price: float) -> dict:
        """Record a point-in-time snapshot for later analysis/plotting."""
        row = {
            "t": t,
            "price": price,
            "cash": self.cash,
            "inventory_kg": self.inventory_kg,
            "committed_kg": self.tranches.committed_kg,
            "available_kg": self.tranches.available_kg(),
            "avg_cost_basis": self.avg_cost_basis,
            "cumulative_sales_kg": self.cumulative_sales_kg,
            "cumulative_purchases_kg": self.cumulative_purchases_kg,
            "cumulative_revenue": self.cumulative_revenue,
            "cumulative_replacement_cost": self.cumulative_replacement_cost,
            "realized_pnl": self.realized_pnl(),
            "mark_to_market_pnl": self.mark_to_market_pnl(price),
            "terminal_wealth": self.terminal_wealth(price),
            "restock_events": self.restock_events,
            "failed_sales": self.failed_sales,
        }
        self.history.append(row)
        return row
