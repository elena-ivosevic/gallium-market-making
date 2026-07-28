"""
simulation.py
=============

Phase 1 deliverable (extended in Phase 2, 3, and now Phase 4): the loop that
ties price_process + demand + accounting + a policy together into a single
run.

WHAT ONE STEP DOES (Phase 1/2 mode -- the DEFAULT, unchanged)
------------------------------------------------------------------
1. Advance the price process by one dt -> new mid price.
2. Generate zero or more customer orders for this dt (Poisson).
3. Ask the policy for its current ask quote, passing mid price, inventory,
   cost basis, elapsed/remaining time (t, T, in years), and the price
   process's fractional volatility (sigma) -- policies use whatever subset
   of this they need.
4. Match each customer order against that quote; execute fills against the
   dealer's book (accounting). Insufficient physical inventory = lost sale.
5. Apply the Phase 1 minimal auto-restock rule if inventory is low, using
   the policy's own `restock_markup_frac()`.
6. Snapshot the dealer's state, and record any policy `last_diagnostics`.

WHAT'S DIFFERENT IN PHASE 3 SUPPLY-CHAIN MODE (opt-in via `supply_chain_params`)
------------------------------------------------------------------------------------
Passing a `SupplyChainParams` to the constructor switches steps 4-5 to a
different path, described in `_attempt_fill_phase3` and
`_run_supply_chain_day` below. In short:
  - An order that can't be filled from physical stock alone is accepted as a
    CUSTOMER COMMITMENT (backorder) if existing in-transit shipments'
    expected contribution can plausibly cover it, or triggers an EMERGENCY
    order (faster, costlier) if not -- rather than being an automatic lost
    sale, for MILITARY-LINKED orders specifically (civilian orders are lost
    sales, matching Phase 1/2 -- see the military/civilian addendum below).
  - Restocking is no longer instant: new orders enter a shipment queue with
    a lead time (src/supply_chain.py) and a chance of partial/failed
    delivery, resolved day by day via `SupplyChain.advance_day()`.
  - Every day's tranche state (physical / committed / in-transit / expected /
    available inventory) is recorded in `policy_diagnostics`-style history
    (`self.tranche_history`) for later analysis.

MILITARY/CIVILIAN ADDENDUM (bundled into Phase 3 supply-chain mode)
------------------------------------------------------------------------
Orders are tagged `military_linked`; civilian orders that can't be filled
from physical stock are LOST SALES (matching Phase 1/2 exactly). Only
military-linked orders roll into a committed backlog, with emergency
shortfall coverage routed specifically through the (less reliable) military
supply channel. See `_attempt_fill_phase3` for the full mechanism and
docs/assumptions_register.md, Section 10, for the register rows.

WHAT'S NEW IN PHASE 4 REGIME MODE (opt-in via `regime_params`)
--------------------------------------------------------------------
Passing a `RegimeParams` to the constructor activates a fourth layer:
  - A `RegimeSwitcher` (src/regimes.py) steps a four-state Markov chain
    (Normal/Delayed/Severe/Recovery) once per day.
  - The price process's jump intensity/size multipliers, the supply chain's
    civilian AND military reliability, the demand process's arrival-rate
    multiplier, and the Hawkes excitation strength are all read from the
    CURRENT regime before that day's price step, order generation, and
    shipment resolution -- so a Severe regime genuinely produces bigger/more
    frequent price jumps, less reliable shipments (especially military-
    channel), and more clustered demand, all at once, from one shared
    regime state.
  - Demand switches from Phase 1-3's single aggregate Poisson process to
    `SectorHawkesOrderFlow` (src/demand.py): four sectors, each with its own
    arrival rate, order size, WTP dispersion, and military-linked share, plus
    a shared Hawkes excitation term for panic clustering, plus
    military-linked orders drawing from a wider, higher willingness-to-pay
    distribution (the register's previously-flagged price-sensitivity gap,
    now closed -- see src/demand.py's module docstring).
  - Regime mode REQUIRES supply-chain mode (military-channel reliability has
    nothing to modulate without it) -- if `regime_params` is given without
    `supply_chain_params`, a default `SupplyChainParams()` is created
    automatically, so the two don't have to be wired up by hand every time.

Phase 1/2 usage (no `supply_chain_params`, no `regime_params`) is COMPLETELY
UNCHANGED -- every existing test that constructs a `Simulation` without these
arguments exercises the exact same code path as before Phase 3/4 existed.
Phase 3 usage (supply_chain_params only, no regime_params) is ALSO UNCHANGED
from how it worked before Phase 4 existed -- regimes are strictly additive.

A DELIBERATE PHASE 3 SIMPLIFICATION (explicit, not hidden)
----------------------------------------------------------------
Phase 3's fill logic never turns away a MILITARY-LINKED order the policy
already agreed to price: if physical and expected supply can't cover it, the
simulation places an emergency order rather than reject the sale outright.
This means military-linked `failed_sales` should rarely if ever occur. A
real dealer might sometimes decline rather than scramble, but modeling that
decision is deferred (there's no register-backed parameter yet for "how much
emergency cost is too much to bear").

WHY THIS STRUCTURE
-------------------
Every later, more sophisticated policy (Avellaneda-Stoikov, scarcity-adjusted,
DP) plugs into the exact same loop by implementing the same `quote_ask` /
`restock_markup_frac` interface. This is what makes the Phase 8 "matched
Monte Carlo" possible: the same price path, the same customer arrivals, and
the same random seeds can be replayed against different policies, because
none of that generation logic lives inside the policy itself. The generic
`last_diagnostics` hook (Phase 2) means the simulation loop never needs an
`if isinstance(policy, AvellanedaStoikovPolicy)` branch -- any current or
future policy can expose whatever internal state is worth plotting later.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Single commodity, single dealer, no competitors.
- Time step is daily; intraday dynamics are not modeled.
- `T` (trading horizon, years) is simply `n_steps * dt` -- i.e., the
  simulation's own length. This is the natural choice for reproducing
  Avellaneda-Stoikov's finite-horizon assumption, but it means the "horizon"
  isn't derived from any real dealer planning cycle -- register Section 5,
  "Trading horizon length" row.
- Phase 3's emergency-order-always-covers-it assumption for military-linked
  orders (see above).
- Regime transitions are checked once per day (see src/regimes.py); no
  intra-day regime changes.
- The Hawkes excitation state is shared across sectors, not per-sector (see
  src/demand.py's module docstring for why).

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Nothing else runs -- this is the orchestrator. Without it you have isolated,
individually-testable components but no actual simulation.
"""

from dataclasses import dataclass, field
import numpy as np

from src.price_process import GalliumPriceProcess, PriceProcessParams
from src.demand import (
    PoissonOrderFlow, DemandParams,
    SectorHawkesOrderFlow, SectorParams, MilitaryElasticityParams, HawkesParams,
)
from src.accounting import DealerBook, AccountingParams
from src.supply_chain import SupplyChain, SupplyChainParams
from src.regimes import RegimeSwitcher, RegimeParams
from src.policies.priority_overlay import PriorityOverlay, PriorityOverlayParams


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
        supply_chain_params: SupplyChainParams = None,
        regime_params: RegimeParams = None,
        sectors: list[SectorParams] = None,
        military_elasticity: MilitaryElasticityParams = None,
        hawkes_params: HawkesParams = None,
        priority_overlay_params: PriorityOverlayParams = None,
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
        self.book = DealerBook(accounting_params or AccountingParams())

        # Phase 4: regime mode requires supply-chain mode (military-channel
        # reliability has nothing to modulate without it). Auto-create a
        # default SupplyChainParams() if the caller only supplied
        # regime_params -- documented, not a silent surprise.
        if regime_params is not None and supply_chain_params is None:
            supply_chain_params = SupplyChainParams()

        # Phase 3: supply-chain mode is entirely opt-in. If no
        # supply_chain_params is given, self.supply_chain stays None and
        # run() takes the exact Phase 1/2 code path, unchanged.
        supply_chain_seed = None if rng_seed is None else rng_seed + 2
        self.supply_chain = (
            SupplyChain(supply_chain_params, seed=supply_chain_seed)
            if supply_chain_params is not None
            else None
        )

        # Phase 4: regime-switching is entirely opt-in. If regime_params is
        # None, self.regime_switcher stays None and run() never touches
        # regime-dependent multipliers -- Phase 1-3 behavior is identical to
        # before Phase 4 existed.
        regime_seed = None if rng_seed is None else rng_seed + 3
        self.regime_switcher = (
            RegimeSwitcher(regime_params, seed=regime_seed) if regime_params is not None else None
        )

        # Phase 4: demand source. Sector+Hawkes flow only when regime mode is
        # active; otherwise the exact Phase 1-3 PoissonOrderFlow, unchanged.
        if self.regime_switcher is not None:
            self.order_flow = SectorHawkesOrderFlow(
                sectors=sectors, military_elasticity=military_elasticity,
                hawkes_params=hawkes_params, seed=demand_seed,
            )
        else:
            self.order_flow = PoissonOrderFlow(demand_params or DemandParams(), seed=demand_seed)

        self.backorder_queue: list[dict] = []  # only used in Phase 3 mode
        self.tranche_history: list[dict] = []  # only populated in Phase 3 mode
        self.stockout_events = 0               # only incremented in Phase 3 mode
        self.total_military_kg_committed = 0.0  # (addendum) cumulative kg ever reserved
                                                 # via a military-linked commitment -- used
                                                 # to compute an honest DELIVERY-confirmed
                                                 # rate, not just an acceptance rate (see
                                                 # "military_fill_rate" caveat in run()'s
                                                 # result dict)
        self.regime_history: list[dict] = []    # (Phase 4) only populated in regime mode

        # Phase 5: priority-allocation overlay is entirely opt-in. If
        # priority_overlay_params is None, self.priority_overlay stays None
        # and run() never reorders a day's fill-attempt sequence -- default
        # arrival-order processing, unchanged from Phase 1-4.
        overlay_seed = None if rng_seed is None else rng_seed + 4
        self.priority_overlay = (
            PriorityOverlay(priority_overlay_params, seed=overlay_seed)
            if priority_overlay_params is not None
            else None
        )

        self.order_log: list[dict] = []
        self.policy_diagnostics: list[dict] = []

    def run(self) -> dict:
        dt = self.price_process.p.dt
        horizon_years = self.config.n_steps * dt
        sigma_frac = self.price_process.p.sigma

        for t in range(self.config.n_steps):
            # Phase 4: step the regime BEFORE anything else that day, so
            # today's price jump, demand, and shipment reliability all react
            # to today's regime, not yesterday's.
            if self.regime_switcher is not None:
                if t > 0:  # regime starts at its initial_regime on day 0
                    self.regime_switcher.step()
                jump_intensity_mult = self.regime_switcher.jump_intensity_multiplier()
                jump_size_mult = self.regime_switcher.jump_size_multiplier()
                # Supply-chain reliability is updated for TODAY's shipment
                # resolutions and any new orders placed today.
                self.supply_chain.p.reliability = self.regime_switcher.civilian_reliability()
                self.supply_chain.p.reliability_military = self.regime_switcher.military_reliability()
                price = self.price_process.step(
                    regime_jump_intensity_multiplier=jump_intensity_mult,
                    regime_jump_size_multiplier=jump_size_mult,
                )
                orders = self.order_flow.generate_orders(
                    mid_price=price, dt=dt,
                    demand_intensity_multiplier=self.regime_switcher.demand_intensity_multiplier(),
                    hawkes_excitation_strength=self.regime_switcher.hawkes_excitation(),
                )
                self.regime_history.append(
                    {
                        "t": t,
                        "regime": self.regime_switcher.current_regime,
                        "civilian_reliability": self.supply_chain.p.reliability,
                        "military_reliability": self.supply_chain.p.reliability_military,
                        "excitation": getattr(self.order_flow, "excitation", None),
                    }
                )
            else:
                # Phase 1-3 path, unchanged: no regime multipliers, flat demand.
                price = self.price_process.step()
                orders = self.order_flow.generate_orders(mid_price=price)

            # Phase 5: priority-allocation overlay reorders TODAY's fill
            # attempts (never the quote itself) -- see policies/priority_overlay.py.
            if self.priority_overlay is not None:
                orders = self.priority_overlay.order_sequence(orders)

            ask = self.policy.quote_ask(
                mid_price=price,
                inventory_kg=self.book.inventory_kg,
                avg_cost_basis=self.book.avg_cost_basis,
                t=t * dt,
                T=horizon_years,
                sigma=sigma_frac,
                # Phase 5: optional physical-market state for
                # ScarcityAdjustedASPolicy's five premiums (register Section
                # 12.1). Every other policy ignores these via **_ignored_state.
                available_kg=self.book.available_kg() if self.supply_chain is not None else None,
                safety_stock_kg=self.book.p.safety_stock_kg,
                replacement_markup_frac=(
                    self.supply_chain.replacement_markup_frac(
                        self.book.available_kg(), self.book.p.safety_stock_kg
                    )
                    if self.supply_chain is not None
                    else None
                ),
                civilian_reliability=(
                    self.supply_chain.p.reliability if self.supply_chain is not None else None
                ),
                committed_kg=self.book.tranches.committed_kg if self.supply_chain is not None else 0.0,
                regime_severity=self._regime_severity(),
                # Phase 6: the DP policy's discrete state lookup needs the
                # actual regime NAME (not just the continuous severity
                # score above). Every other policy ignores this via
                # **_ignored_state.
                regime_name=(
                    self.regime_switcher.current_regime if self.regime_switcher is not None else None
                ),
            )

            # Phase 6: policies that expose wants_emergency_purchase() (the
            # DP policy's "purchase emergency inventory" action) can trigger
            # a real emergency order, independent of Phase 3's own
            # reorder-point logic. Checked once per day, right after the
            # quote -- this is the ONLY way a policy's chosen ACTION (as
            # opposed to its quoted PRICE) reaches back into the supply
            # chain; no earlier policy has this hook.
            if self.supply_chain is not None and getattr(
                self.policy, "wants_emergency_purchase", lambda: False
            )():
                markup = self.supply_chain.replacement_markup_frac(
                    self.book.available_kg(), self.book.p.safety_stock_kg
                ) * self.supply_chain.p.emergency_cost_multiplier
                unit_cost = price * (1.0 + markup)
                order_kg = self.book.p.restock_amount_kg
                shipment = self.supply_chain.place_order(order_kg, emergency=True, channel="civilian")
                shipment.unit_cost_locked = unit_cost
                self.book.pay_for_supply_order(order_kg, unit_cost)

            for order in orders:
                want_fill = ask <= order.willingness_to_pay
                fill_type = "rejected"
                filled = False
                if want_fill:
                    if self.supply_chain is None:
                        # Phase 1/2 path, unchanged: insufficient physical
                        # inventory simply loses the sale.
                        filled = self.book.record_sale(order.size_kg, ask)
                        fill_type = "immediate" if filled else "rejected"
                    else:
                        filled, fill_type = self._attempt_fill_phase3(order, ask, price)

                self.order_log.append(
                    {
                        "t": t,
                        "price": price,
                        "ask": ask,
                        "size_kg": order.size_kg,
                        "willingness_to_pay": order.willingness_to_pay,
                        "military_linked": order.military_linked,
                        "sector": order.sector,
                        "filled": filled,
                        "fill_type": fill_type,
                    }
                )

            if self.supply_chain is None:
                # Phase 1/2 path, unchanged.
                markup_frac = self.policy.restock_markup_frac(
                    inventory_kg=self.book.inventory_kg,
                    avg_cost_basis=self.book.avg_cost_basis,
                )
                self.book.maybe_auto_restock(price, markup_frac)
            else:
                self._run_supply_chain_day(price)

            self.book.snapshot(t, price)

            if self.supply_chain is not None:
                self.tranche_history.append(
                    {
                        "t": t,
                        "physical_kg": self.book.tranches.physical_kg,
                        "committed_kg": self.book.tranches.committed_kg,
                        "in_transit_kg": self.supply_chain.in_transit_kg(),
                        "expected_kg": self.supply_chain.expected_kg(),
                        "available_kg": self.book.available_kg(),
                    }
                )

            # Generic diagnostics hook (Phase 2): any policy may expose a
            # `last_diagnostics` dict describing its own internal quoting
            # state (reservation price, bid, spread, etc.). The simulation
            # loop does not need to know which policy is running to record it.
            diag = getattr(self.policy, "last_diagnostics", None)
            if diag:
                row = dict(diag)
                row["t"] = t
                self.policy_diagnostics.append(row)

        final_price = self.price_process.price
        result = {
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
            "policy_diagnostics": self.policy_diagnostics,
            "price_path": self.price_process.history,
        }

        if self.supply_chain is not None:
            military_orders = [o for o in self.order_log if o["military_linked"]]
            civilian_orders = [o for o in self.order_log if not o["military_linked"]]
            military_filled = sum(1 for o in military_orders if o["filled"])
            civilian_filled = sum(1 for o in civilian_orders if o["filled"])

            result.update(
                {
                    "tranche_history": self.tranche_history,
                    "shipments_placed": self.supply_chain.total_shipments_placed,
                    "emergency_orders_placed": self.supply_chain.total_emergency_orders,
                    "failed_deliveries": self.supply_chain.total_failed_deliveries,
                    "kg_lost_to_failed_deliveries": self.supply_chain.total_kg_lost_to_failure,
                    "stockout_events": self.stockout_events,
                    "final_backorder_queue_kg": sum(b["kg"] for b in self.backorder_queue),
                    "cumulative_backlog_penalty": self.book.cumulative_backlog_penalty,
                    "cumulative_lost_delivery_cost": self.book.cumulative_lost_delivery_cost,
                    # (addendum, register Section 10) military vs. civilian breakdown --
                    # the headline comparison this project's second core research
                    # question depends on. n_orders/n_filled above remain the pooled
                    # totals for backward compatibility with Phase 1/2 result-dict shape.
                    #
                    # CAVEAT, found during Phase 3 addendum integration testing:
                    # "military_fill_rate" measures whether an order was ACCEPTED
                    # (immediate sale, backordered, or emergency-backordered) -- NOT
                    # whether the promised gallium was ever actually delivered. A
                    # military order accepted into the backorder queue counts as
                    # "filled" here even if it is still sitting unfulfilled at the
                    # end of the simulation. This overstates true protection. Use
                    # "military_kg_delivery_rate" below for a more honest (though
                    # still aggregate, not per-order) measure of what fraction of
                    # committed military kg was actually delivered by simulation end.
                    "n_military_orders": len(military_orders),
                    "n_military_filled": military_filled,
                    "military_fill_rate": (military_filled / len(military_orders)) if military_orders else None,
                    "total_military_kg_committed": self.total_military_kg_committed,
                    "military_kg_delivery_rate": (
                        1.0 - (sum(b["kg"] for b in self.backorder_queue) / self.total_military_kg_committed)
                        if self.total_military_kg_committed > 0
                        else None
                    ),
                    "n_civilian_orders": len(civilian_orders),
                    "n_civilian_filled": civilian_filled,
                    "civilian_fill_rate": (civilian_filled / len(civilian_orders)) if civilian_orders else None,
                    "shipments_by_channel": dict(self.supply_chain.total_shipments_by_channel),
                    "failed_deliveries_by_channel": dict(
                        self.supply_chain.total_failed_deliveries_by_channel
                    ),
                    "kg_lost_by_channel": dict(self.supply_chain.total_kg_lost_by_channel),
                }
            )

        if self.regime_switcher is not None:
            sector_fill_rates = {}
            for sector_name in {o["sector"] for o in self.order_log}:
                sector_orders = [o for o in self.order_log if o["sector"] == sector_name]
                sector_filled = sum(1 for o in sector_orders if o["filled"])
                sector_fill_rates[sector_name] = {
                    "n_orders": len(sector_orders),
                    "n_filled": sector_filled,
                    "fill_rate": sector_filled / len(sector_orders) if sector_orders else None,
                }
            result.update(
                {
                    "regime_history": self.regime_history,
                    "regime_days": dict(self.regime_switcher.regime_days),
                    "sector_fill_rates": sector_fill_rates,
                }
            )

        return result

    # ---- Phase 3 helpers ----------------------------------------------------

    def _attempt_fill_phase3(self, order, ask: float, price: float) -> tuple[bool, str]:
        """
        Decide how to fill an order the policy has already agreed to price
        (ask <= willingness_to_pay), in supply-chain mode. As of the
        military/civilian addendum (register Section 10), this now branches
        on `order.military_linked`:

          1. If physical inventory covers it: immediate sale, either channel
             (physical stock is fungible once delivered -- see below).
          2. Else if CIVILIAN: LOST SALE. Register Section 10, "Unfilled
             order treatment": civilian orders that can't be filled from
             physical stock are rejected, matching Phase 1/2 behavior
             exactly -- civilian demand is treated as discretionary spot
             demand that walks away, not a standing commitment.
          3. Else (MILITARY-LINKED): accept as a customer commitment
             (backorder) if physical + expected pipeline (net of existing
             commitments) plausibly covers it -- gallium is fungible once
             delivered, so ANY pending shipment (civilian or military
             channel) counts toward this check, not just military-channel
             ones. If the pipeline can't cover it, place an EMERGENCY order
             specifically through the MILITARY channel (lower reliability,
             register Section 10) to close the gap, then accept the
             commitment anyway -- this project does not model the dealer
             ever declining a military-linked order it already agreed to
             price (see "A deliberate Phase 3 simplification" in the module
             docstring; that simplification now applies only to the
             military-linked branch, not civilian).

        WHY EMERGENCY MILITARY-SHORTFALL COVERAGE USES THE MILITARY CHANNEL
        -------------------------------------------------------------------------
        A shipment procured specifically to fulfill a military-linked
        commitment is itself plausibly subject to the same military-end-use
        export-control scrutiny (phase0_research_notes.md, Section 2) as the
        underlying customer demand -- so it is resolved against the lower
        military-channel reliability, not the civilian default. This is the
        mechanism that makes the military/civilian distinction actually bite
        analytically: the supply route the dealer is forced to use to
        protect military-linked commitments is itself less reliable than its
        ordinary civilian restocking.
        """
        book = self.book
        size = order.size_kg

        if book.tranches.physical_kg >= size:
            filled = book.record_sale(size, ask)
            return filled, ("immediate" if filled else "rejected")

        if not order.military_linked:
            # Register Section 10: civilian unfilled orders are lost sales.
            book.failed_sales += 1
            return False, "rejected"

        pipeline_available = (
            book.tranches.physical_kg + self.supply_chain.expected_kg() - book.tranches.committed_kg
        )
        if pipeline_available >= size:
            book.reserve_commitment(size)
            self.backorder_queue.append({"kg": size, "price": ask, "military_linked": True})
            self.total_military_kg_committed += size
            return True, "backordered"

        # Not enough even in the combined pipeline: place an emergency order,
        # specifically through the MILITARY channel (see docstring), to cover
        # the shortfall, then accept the commitment anyway.
        shortfall = max(0.0, size - max(0.0, pipeline_available))
        if shortfall > 0:
            markup = self.supply_chain.replacement_markup_frac(
                book.available_kg(), self.book.p.safety_stock_kg
            ) * self.supply_chain.p.emergency_cost_multiplier
            unit_cost = price * (1.0 + markup)
            shipment = self.supply_chain.place_order(shortfall, emergency=True, channel="military")
            shipment.unit_cost_locked = unit_cost
            book.pay_for_supply_order(shortfall, unit_cost)
            self.stockout_events += 1

        book.reserve_commitment(size)
        self.backorder_queue.append({"kg": size, "price": ask, "military_linked": True})
        self.total_military_kg_committed += size
        return True, "emergency_backordered"

    def _run_supply_chain_day(self, price: float) -> None:
        """
        Resolve any shipments due today, apply delivered kg first to the
        backorder queue (FIFO) and then to free physical stock, and place a
        new NORMAL order if the dealer's INVENTORY POSITION -- physical +
        in-transit - committed, a standard inventory-theory concept distinct
        from available_kg() -- has fallen to/below the reorder point (see
        `_reorder_point_kg`).

        WHY INVENTORY POSITION, NOT available_kg(), DRIVES THE REORDER DECISION
        --------------------------------------------------------------------------
        An earlier version of this method used `book.available_kg()` (physical
        - committed - safety stock) directly as the reorder trigger. Because
        that figure ignores shipments ALREADY placed and in transit, it stayed
        negative for the entire ~2-week lead time after the first order was
        placed, causing a NEW 150kg order to be placed on every single one of
        those days -- a duplicate-ordering bug that produced multi-million-
        dollar simulated losses in an early Phase 3 integration run (see
        docs/assumptions_register.md, Section 9). Standard inventory theory
        avoids exactly this failure mode by reordering against "inventory
        position" (on hand + on order - backordered), not on-hand stock alone.
        `available_kg()` remains the right figure for the replacement-cost
        curvature and for reporting/plotting "what can I sell right now,"
        but it is the wrong figure to gate new orders on.
        """
        book = self.book
        resolved = self.supply_chain.advance_day()

        for shipment in resolved:
            if shipment.delivered_kg <= 0:
                lost_kg = shipment.kg_ordered
            else:
                book.receive_delivery(shipment.delivered_kg, shipment.unit_cost_locked)
                lost_kg = shipment.kg_ordered - shipment.delivered_kg

            if lost_kg > 1e-9:
                # The kg that was paid for (pay_for_supply_order, at order
                # time) but never arrived is a sunk cost -- see
                # accounting.py's record_lost_delivery_cost docstring for why
                # this must be recognized explicitly, not left to silently
                # vanish from realized_pnl/mark_to_market_pnl.
                book.record_lost_delivery_cost(lost_kg * shipment.unit_cost_locked)

            if shipment.delivered_kg <= 0:
                continue

            remaining = shipment.delivered_kg
            while remaining > 1e-9 and self.backorder_queue:
                first = self.backorder_queue[0]
                portion = min(first["kg"], remaining)
                delivered_amt = book.deliver_against_commitment(portion, first["price"])
                first["kg"] -= delivered_amt
                remaining -= delivered_amt
                if first["kg"] <= 1e-9:
                    self.backorder_queue.pop(0)
                if delivered_amt <= 0:
                    break  # avoid an infinite loop if nothing more can be delivered

        inventory_position = (
            book.tranches.physical_kg
            + self.supply_chain.in_transit_kg()
            - book.tranches.committed_kg
        )
        reorder_point_kg = self._reorder_point_kg()
        if inventory_position <= reorder_point_kg:
            markup = self.supply_chain.replacement_markup_frac(
                book.available_kg(), book.p.safety_stock_kg
            )
            unit_cost = price * (1.0 + markup)
            order_kg = book.p.restock_amount_kg
            # Normal (non-emergency) restocking routes through the CIVILIAN
            # channel -- it is ordinary commercial replenishment, not
            # procurement specifically to cover a military-linked shortfall
            # (see _attempt_fill_phase3's docstring for the emergency case).
            shipment = self.supply_chain.place_order(order_kg, emergency=False, channel="civilian")
            shipment.unit_cost_locked = unit_cost
            book.pay_for_supply_order(order_kg, unit_cost)

        # (Addendum, register Section 10) Accrue the daily backlog penalty on
        # every military-linked commitment still outstanding at day's end,
        # valued against the price locked in when each backorder was accepted.
        if self.backorder_queue:
            total_backlog_value = sum(b["kg"] * b["price"] for b in self.backorder_queue)
            penalty = total_backlog_value * self.supply_chain.p.backlog_penalty_frac_per_day
            if penalty > 0:
                book.record_backlog_penalty(penalty)

    def _reorder_point_kg(self) -> float:
        """
        Standard inventory-theory reorder point: expected demand during the
        supply lead time, plus the safety-stock buffer itself --

            reorder_point = (demand_rate_per_day * lead_time_days) + safety_stock_kg

        WHY NOT JUST TRIGGER AT safety_stock_kg DIRECTLY
        ------------------------------------------------------
        An earlier version triggered a new order exactly when inventory
        position fell to `safety_stock_kg`. But `available_kg()` (used for
        the replacement-cost markup) is ALSO defined relative to
        `safety_stock_kg` -- so triggering at that exact same level meant
        `available_kg()` was at or near zero at the moment of EVERY reorder,
        which put nearly every normal restock at the markup curve's worst
        (capped) rate, not just genuine emergencies. Reordering earlier --
        with enough of a cushion to cover expected demand across the lead
        time -- is precisely what the reorder-point formula is FOR: it exists
        so that, in typical conditions, the new shipment arrives before the
        buffer is actually breached. This is a standard, textbook inventory-
        management formula (not a new judgment-call parameter): it is
        DERIVED from `safety_stock_kg`, `lead_time_days`, and the demand
        process's own arrival rate and order size, all of which already have
        register rows -- see docs/assumptions_register.md, Section 9.

        This uses the demand process's arrival rate assuming every generated
        order is filled (a conservative overestimate of true demand, since
        the real fill rate is below 100% -- see any policy's fill-rate
        results). That conservatism is deliberate: better to reorder slightly
        early than to under-provision the lead-time buffer.

        (Phase 4) For `SectorHawkesOrderFlow`, demand rate is summed across
        all sectors' base arrival rates * mean order size -- the Hawkes
        excitation term and regime demand multiplier are deliberately NOT
        included here (excitation is a short-lived spike, not a sustained
        rate, and folding the regime multiplier in would make the reorder
        point itself regime-dependent in a way that's hard to reason about
        -- kept as a flagged simplification, not a hidden one).
        """
        dt = self.price_process.p.dt
        if isinstance(self.order_flow, SectorHawkesOrderFlow):
            demand_kg_per_day = sum(
                s.arrival_rate_per_year * s.order_size_mean_kg for s in self.order_flow.sectors
            ) * dt
        else:
            demand_kg_per_day = (
                self.order_flow.p.arrival_rate_per_year * self.order_flow.p.order_size_mean_kg * dt
            )
        lead_time_demand_kg = demand_kg_per_day * self.supply_chain.p.lead_time_days
        return self.book.p.safety_stock_kg + lead_time_demand_kg

    def _regime_severity(self) -> float:
        """
        (Phase 5) A bounded [0, 1] severity signal for
        ScarcityAdjustedASPolicy's regime premium (register Section 12.1).
        Normal=0, Delayed=Recovery=0.5, Severe=1.0 -- a coarser mapping than
        regimes.py's own per-regime multiplier dictionaries, deliberately:
        this premium is meant to be a simple, direct "how bad is it right
        now" signal, distinct from (not redundant with) the other four
        premiums, which each already react to regime indirectly through
        reliability and scarcity. Returns 0.0 outside regime mode.
        """
        if self.regime_switcher is None:
            return 0.0
        severity_map = {"normal": 0.0, "delayed": 0.5, "severe": 1.0, "recovery": 0.5}
        return severity_map.get(self.regime_switcher.current_regime, 0.0)
