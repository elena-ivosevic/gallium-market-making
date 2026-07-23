"""
policies/fixed_spread.py
========================

Phase 1 deliverable: Baseline Strategy (the minimum bar every later policy
must beat).

MODEL
-----
Register Section 6 ("Fixed baseline (non-adaptive) policy") specifies TWO
constant spreads for this policy, not one:

    ask = mid_price * (1 + ask_spread_frac)     -- quoted to customers
    bid_markup_frac                             -- paid when the dealer
                                                    restocks from the supply
                                                    market (see note below)

Neither spread ever changes based on inventory, regime, volatility, or
anything else in the simulation -- that is the entire point of this policy.

WHY THERE IS A "BID" MARKUP BUT NO CUSTOMER-FACING BID QUOTE
------------------------------------------------------------
The register's "Fixed bid spread" row describes a dealer's constant buy-side
markdown. In a typical two-sided market maker, that would be a bid quoted TO
customers who want to sell. Phase 1's demand model (src/demand.py) only
generates customer BUY requests -- there is no customer sell-side order flow
yet (e.g. recyclers or customers offloading excess stock), so there is
nothing for a customer-facing bid to quote against.

Instead, this Phase 1 implementation repurposes the "Fixed bid spread"
concept as the markup the dealer pays when restocking from the external
supply market (src/accounting.py's `restock`). This is a deliberate,
flagged reinterpretation, not a silent substitution: if/when a customer
sell-side flow is added, `bid_markup_frac` should be split into two
genuinely distinct parameters (a customer-facing bid vs. a supplier
procurement premium), logged as separate register rows.

WHY THIS EXISTS
----------------
Every more sophisticated policy in this project (Avellaneda-Stoikov,
scarcity-adjusted AS, dynamic programming) needs a floor to beat. If a
"smart" policy cannot outperform a dealer who just charges a constant
markup, the added complexity is not earning its keep. This is intentionally
the dumbest reasonable policy: no state is used at all besides the current
price.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Ignores inventory level entirely -- will keep quoting the same spread even
  while running low on stock (no scarcity protection).
- Ignores volatility, jump risk, and regime entirely.
- A constant spread that is "too tight" in calm periods may also be "too
  tight" during a severe regime, and a spread that is safe during a severe
  regime is needlessly wide (and uncompetitive) during calm periods. This
  is the exact failure mode later phases are built to fix.
- `bid_markup_frac` is currently a stand-in for supplier procurement cost,
  not a genuine customer-facing bid (see note above) -- a real limitation,
  not just a naming quirk.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
There is no baseline comparison point. Every "our smarter model made more
money" claim later in the project needs this benchmark to make that claim
meaningful.
"""

from dataclasses import dataclass


@dataclass
class FixedSpreadParams:
    ask_spread_frac: float = 0.04    # constant markup over mid price quoted to customers
                                      # (register Section 6, "Fixed ask spread" -- judgment
                                      # call, deliberately naive by design)
    bid_markup_frac: float = 0.03    # constant markup the dealer pays over spot when
                                      # restocking (register Section 6, "Fixed bid spread",
                                      # reinterpreted as a supplier procurement premium --
                                      # see module docstring)


class FixedSpreadPolicy:
    """The simplest possible dealer: quote mid * (1 + ask_spread_frac) to
    customers, always; pay spot * (1 + bid_markup_frac) to restock, always."""

    def __init__(self, params: FixedSpreadParams):
        self.p = params

    def quote_ask(self, mid_price: float, **_ignored_state) -> float:
        """
        Return the ask price. Accepts **_ignored_state so the simulation
        loop can pass inventory/regime/etc. to every policy uniformly --
        this policy simply ignores all of it, which is the point.
        """
        return mid_price * (1.0 + self.p.ask_spread_frac)

    def restock_markup_frac(self, **_ignored_state) -> float:
        """
        Markup paid over spot when the simulation's auto-restock rule fires.
        Part of the shared policy interface (see src/simulation.py) so any
        policy -- fixed-spread now, Avellaneda-Stoikov and scarcity-adjusted
        later -- can express its own restock-cost view instead of the
        simulation loop reaching into policy-internal fields.
        """
        return self.p.bid_markup_frac
