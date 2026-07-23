"""
simulation.py
=============

Phase 1 deliverable: the loop that ties price_process + demand + accounting
+ a policy together into a single run.

WHAT ONE STEP DOES
------------------
1. Advance the price process by one dt -> new mid price.
2. Generate zero or more customer orders for this dt (Poisson).
3. Ask the policy for its current ask quote (policies may use mid price,
   inventory, or nothing at all, depending on sophistication).
4. Match each customer order against that quote; execute fills against the
   dealer's book (accounting).
5. Apply the Phase 1 minimal auto-restock rule if inventory is low.
6. Snapshot the dealer's state for later analysis.

WHY THIS STRUCTURE
-------------------
Every later, more sophisticated policy (Avellaneda-Stoikov, scarcity-adjusted,
DP) plugs into the exact same loop by implementing the same `quote_ask`
interface. This is what makes the Phase 8 "matched Monte Carlo" possible:
the same price path, the same customer arrivals, and the same random seeds
can be replayed against different policies, because none of that generation
logic lives inside the policy itself.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Single commodity, single dealer, no competitors.
- No sector structure, no regimes, no Hawkes clustering (Phase 4).
- No lead-time supply chain (Phase 3) -- restocking is instant (see
  accounting.py docstring).
- Time step is daily; intraday dynamics are not modeled.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Nothing else runs -- this is the orchestrator. Without it you have isolated,
individually-testable components but no actual simulation.
"""

from dataclasses import dataclass, field
import numpy as np

from src.price_process import GalliumPriceProcess, PriceProcessParams
from src.demand import PoissonOrderFlow, DemandParams
from src.accounting import DealerBook, AccountingParams


@dataclass
class SimulationConfig:
    n_steps: int = 252  # one trading year at daily steps
    seed: int | None = 42


class Simulation:
    def __init__(
        self,
        policy,
        price_params: PriceProcessParams = None,
        demand_params: DemandParams = None,
        accounting_params: AccountingParams = None,
        config: SimulationConfig = None,
    ):
        self.policy = policy
        self.config = config or SimulationConfig()

        rng_seed = self.config.seed
        self.price_process = GalliumPriceProcess(
            price_params or PriceProcessParams(), seed=rng_seed
        )
        # Use a distinct but deterministic sub-seed for demand so that price
        # and demand randomness can be independently re-seeded if needed.
        demand_seed = None if rng_seed is None else rng_seed + 1
        self.order_flow = PoissonOrderFlow(demand_params or DemandParams(), seed=demand_seed)
        self.book = DealerBook(accounting_params or AccountingParams())

        self.order_log: list[dict] = []

    def run(self) -> dict:
        for t in range(self.config.n_steps):
            price = self.price_process.step()

            orders = self.order_flow.generate_orders(mid_price=price)
            ask = self.policy.quote_ask(
                mid_price=price,
                inventory_kg=self.book.inventory_kg,
                avg_cost_basis=self.book.avg_cost_basis,
            )

            for order in orders:
                filled = ask <= order.willingness_to_pay
                if filled:
                    success = self.book.record_sale(order.size_kg, ask)
                    filled = success  # may still fail if insufficient inventory
                self.order_log.append(
                    {
                        "t": t,
                        "price": price,
                        "ask": ask,
                        "size_kg": order.size_kg,
                        "willingness_to_pay": order.willingness_to_pay,
                        "filled": filled,
                    }
                )

            # The restock markup is a dealer POLICY parameter (register Section 6,
            # "Fixed bid spread"), not an accounting-module constant -- see
            # accounting.py and policies/fixed_spread.py docstrings for why.
            # Every policy is expected to implement restock_markup_frac() as
            # part of the shared policy interface.
            markup_frac = self.policy.restock_markup_frac(
                inventory_kg=self.book.inventory_kg,
                avg_cost_basis=self.book.avg_cost_basis,
            )
            self.book.maybe_auto_restock(price, markup_frac)
            self.book.snapshot(t, price)

        final_price = self.price_process.price
        return {
            "final_price": final_price,
            "terminal_wealth": self.book.terminal_wealth(final_price),
            "realized_pnl": self.book.realized_pnl(),
            "mark_to_market_pnl": self.book.mark_to_market_pnl(final_price),
            "cumulative_sales_kg": self.book.cumulative_sales_kg,
            "cumulative_purchases_kg": self.book.cumulative_purchases_kg,
            "restock_events": self.book.restock_events,
            "failed_sales": self.book.failed_sales,
            "n_orders": len(self.order_log),
            "n_filled": sum(1 for o in self.order_log if o["filled"]),
            "history": self.book.history,
            "order_log": self.order_log,
            "price_path": self.price_process.history,
        }
