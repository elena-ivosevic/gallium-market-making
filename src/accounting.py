"""
accounting.py
=============

Phase 1 deliverable: Dealer Accounting + a minimal restock mechanism.

WHAT THIS TRACKS
----------------
- cash                  : USD on hand
- inventory_kg          : physical gallium on hand
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

MINIMAL RESTOCK MECHANISM (A DELIBERATE, FLAGGED SIMPLIFICATION)
-------------------------------------------------------------------
Phase 1 needs *some* way for inventory to replenish, or every policy
trivially runs out of gallium and stops trading. The full supply chain
(lead times, partial/failed deliveries, in-transit vs. committed vs.
expected inventory -- register Section 3, e.g. "Shipment lead time
(Normal)") is explicitly Phase 3 work and is NOT built here.

Instead, Phase 1 uses an immediate, deterministic restock: whenever
inventory drops to or below `restock_threshold_kg` (a placeholder stand-in
for the register's "Safety stock level" row, Section 3), the dealer
instantly buys `restock_amount_kg` at the current spot price plus a markup
supplied by the CALLER (see below), with no delay and no probability of
failure.

This is a simplification, not a finished result. It exists only so Phase 1
policies can be exercised over a full simulation without collapsing to zero
inventory. It should be treated as scaffolding to be torn out and replaced
in Phase 3, not as a model of real supplier behavior.

WHY THE MARKUP IS NOT A FIELD ON AccountingParams
----------------------------------------------------
An earlier draft of this module hard-coded a `replacement_markup_frac` field
directly on AccountingParams, with no corresponding row in
docs/assumptions_register.md -- a rule-#1 violation ("no parameter is added
to code before it has a row here"). The markup a dealer pays to restock is
properly the register's Section 6 "Fixed bid spread" (a dealer POLICY
parameter, not an inventory-mechanics parameter), so `restock()` and
`maybe_auto_restock()` now take the markup as an explicit argument supplied
by whichever policy is running the simulation. See
`src/policies/fixed_spread.py` for where that value now lives, and
`docs/assumptions_register.md`, Section 7, for the logged concrete value.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- No lead time: real shipments take time to arrive; this restock is instant.
- No failure probability: real shipments can fail to arrive; this cannot.
- No distinction between physical / committed / in-transit / expected
  inventory (Phase 3 concept) -- there is only a single inventory_kg number.
- The markup is a constant fraction, not the nonlinear, scarcity-driven
  replacement cost described in later phases (register: "Replacement-cost
  curvature parameter", Section 3).

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Without accounting, there is no way to score a policy -- P&L, inventory
risk, and terminal wealth all come from here. Without the restock stub,
every policy eventually sells out of inventory and the simulation becomes
a trivial "how fast do you sell your starting stock" exercise.
"""

from dataclasses import dataclass, field
import numpy as np


@dataclass
class AccountingParams:
    initial_cash: float = 50_000.0
    initial_inventory_kg: float = 200.0
    restock_threshold_kg: float = 50.0     # trigger restock at/below this level
                                            # (register Section 3: "Safety stock level" --
                                            # judgment call, no fitted dealer policy exists)
    restock_amount_kg: float = 150.0       # amount purchased per restock event (judgment call,
                                            # no register row yet -- flagged for Section 3
                                            # follow-up alongside shipment-lot-size modeling)


class DealerBook:
    """Tracks cash, inventory, and P&L for one dealer/policy over a simulation."""

    def __init__(self, params: AccountingParams):
        self.p = params
        self.cash = float(params.initial_cash)
        self.inventory_kg = float(params.initial_inventory_kg)
        self._initial_capital = self.cash + self.inventory_kg * 0.0  # priced later, see note below
        self.cumulative_purchases_kg = 0.0
        self.cumulative_sales_kg = 0.0
        self.cumulative_revenue = 0.0
        self.cumulative_replacement_cost = 0.0
        self.cumulative_cogs = 0.0  # cost of goods sold, at weighted-average cost basis
        self.avg_cost_basis = 0.0   # running weighted-average cost per kg of held inventory
        self.restock_events = 0
        self.failed_sales = 0       # orders rejected due to insufficient inventory
        self.history: list[dict] = []

    # ---- core operations -------------------------------------------------

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

        `markup_frac` is supplied by the calling policy (register Section 6,
        "Fixed bid spread" for the fixed-spread baseline) -- it is not stored
        on AccountingParams. See module docstring for why.
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

    # ---- P&L / reporting --------------------------------------------------

    def realized_pnl(self) -> float:
        """Cash-basis P&L: revenue - cost of goods sold. Replacement cost is
        already reflected through COGS at the point of sale (weighted-average
        cost basis), so it is not subtracted a second time here."""
        return self.cumulative_revenue - self.cumulative_cogs

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
