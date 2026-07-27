"""
demand.py
=========

Phase 1 deliverable: Basic Customer Order Flow.
Addendum (pre-Phase 4): military-linked order tagging, aggregate/pre-sector.

MODEL
-----
Customers are represented as a homogeneous Poisson arrival process (constant
rate). Each arriving customer:
  1. Wants to BUY gallium from the dealer (Phase 1 only models buy-side
     customer demand; the dealer is the sole seller in this simplified world).
  2. Has a random order size (lognormal, always positive, right-skewed like
     real industrial purchase orders).
  3. Has a private maximum willingness-to-pay (reservation price), drawn
     around the current fair/mid price with some dispersion.
  4. The order EXECUTES only if the dealer's quoted ask price is at or below
     the customer's willingness-to-pay. Otherwise it is rejected (walks away).
  5. (Addendum) Is independently tagged military-linked with probability
     `military_linked_share`, via a per-order Bernoulli draw -- register
     Section 10, "Military-linkage assignment mechanism."

WHY POISSON FIRST (AND WHY IT WILL BE REPLACED LATER)
-------------------------------------------------------
A homogeneous Poisson process is the simplest defensible null model for
"orders arrive independently at some average rate." It has one parameter
(the rate) and is easy to validate, easy to reason about, and is the correct
baseline to which the Phase 4 Hawkes (self-exciting) process must be compared.
Real panic-buying behavior is NOT well described by Poisson because one
urgent order raises the probability of more urgent orders shortly after
(clustering). That is deliberately NOT modeled here; Phase 4 will add it.

WHY EXECUTION IS PRICE-DEPENDENT
-----------------------------------
A dealer's spread only matters economically if quoting a worse price loses
sales. Without a price-dependent fill probability, the fixed-spread baseline
and every later, more sophisticated pricing policy would be indistinguishable
in terms of P&L (nothing would differentiate a wide quote from a narrow one).

MILITARY-LINKED TAGGING: WHY AGGREGATE, NOT PER-SECTOR (addendum scope)
--------------------------------------------------------------------------
The full roadmap design (Phase 4) gives EACH SECTOR its own
military_linked_share (Defense & Aerospace highest, others lower but
nonzero). Sectors do not exist yet in this codebase -- Phase 1 deliberately
kept demand homogeneous ("Sector and end-use distinctions ... are
deliberately deferred to Phase 4"). This addendum uses a SINGLE aggregate
`military_linked_share` applied uniformly to every order, as a placeholder
that unblocks Phase 3's channel-dependent shipment reliability now, without
pretending to have sector-level realism it doesn't have yet. See
docs/assumptions_register.md, Section 10, for the explicit scope note.

WHY THE TAG DOES NOTHING TO WILLINGNESS-TO-PAY (a deliberate, flagged gap)
--------------------------------------------------------------------------------
Military-linked orders in THIS module face the exact same willingness-to-pay
distribution as civilian orders -- there is no elasticity difference yet
(that is the roadmap's Phase 4 "Military demand price-sensitivity" row, not
built here). This means the tag currently only matters for two things
downstream: shipment-channel reliability and unfilled-order treatment (both
in src/supply_chain.py and src/simulation.py) -- NOT for pricing. This is a
real, intentional limitation, not an oversight: it is exactly the gap that
motivates this project's second core research question (does pricing alone
protect military-critical supply, or does it take a non-price mandate?) --
answering that honestly requires being explicit about what does and doesn't
differ between the two channels at each phase.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Arrival rate is constant; no sector structure yet (Phase 4).
- Willingness-to-pay is drawn independently from the price process itself
  (except that it is centered on the current mid). In reality, willingness-
  to-pay likely also depends on the customer's own inventory position and
  urgency -- not modeled until sectors + Hawkes arrive in Phase 4.
- Execution is a hard threshold (fill if ask <= WTP), not a smooth/probabilistic
  function of price. A smoother fill-probability curve is a reasonable future
  refinement but adds a parameter with no current empirical basis to set it.
- All customers are identical in distribution; no persistent customer identity
  across time.
- Military-linked tagging is aggregate/pre-sector and does not (yet) affect
  willingness-to-pay -- see above.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Without customer arrivals, the dealer never sells anything: there is no
revenue, no inventory depletion, and no way to differentiate policies. The
whole point of a market-making simulation is quote-dependent trade execution,
which lives here. Without the military-linked tag specifically, Phase 3's
channel-dependent shipment reliability and backlog-vs-lost-sale treatment
have nothing to route orders by.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class DemandParams:
    arrival_rate_per_year: float = 250.0   # avg customers/year, judgment call (Phase 0 register)
    order_size_mean_kg: float = 25.0       # mean order size (lognormal), judgment call
    order_size_sigma: float = 0.6          # lognormal shape parameter (right skew)
    wtp_spread_frac: float = 0.05          # customer WTP dispersion as fraction of mid price
    military_linked_share: float = 0.15    # (addendum) register Section 10 -- aggregate,
                                            # pre-sector fraction of orders tagged military-linked
    dt: float = 1.0 / 252.0


@dataclass
class CustomerOrder:
    size_kg: float
    willingness_to_pay: float
    military_linked: bool = False
    filled: bool = False
    fill_price: float = 0.0


class PoissonOrderFlow:
    """Generates zero or more customer buy orders per simulation step."""

    def __init__(self, params: DemandParams, seed: int | None = None):
        self.p = params
        self.rng = np.random.default_rng(seed)

    def generate_orders(self, mid_price: float) -> list[CustomerOrder]:
        """
        Draw the number of arrivals for this dt via Poisson, then generate
        one CustomerOrder per arrival. Orders are NOT yet matched against a
        dealer quote here -- that happens in the policy/simulation loop so
        that different pricing policies can be tested against the identical
        set of arriving orders (needed for the matched Monte Carlo in Phase 8).

        Each order is independently tagged military_linked with probability
        `military_linked_share` (register Section 10). This tagging draw
        uses the SAME rng as order size/WTP, in the same fixed order per
        order (size, then WTP, then the military tag) so that a given seed
        always reproduces the identical set of orders regardless of what
        downstream code does with the tag -- important for the matched
        Monte Carlo comparisons this project relies on throughout.
        """
        lam = self.p.arrival_rate_per_year * self.p.dt
        n_orders = self.rng.poisson(lam)
        orders = []
        for _ in range(n_orders):
            size = self.rng.lognormal(
                mean=np.log(self.p.order_size_mean_kg) - 0.5 * self.p.order_size_sigma**2,
                sigma=self.p.order_size_sigma,
            )
            wtp = mid_price * (1.0 + self.rng.normal(0.0, self.p.wtp_spread_frac))
            military_linked = bool(self.rng.random() < self.p.military_linked_share)
            orders.append(
                CustomerOrder(
                    size_kg=float(size),
                    willingness_to_pay=float(wtp),
                    military_linked=military_linked,
                )
            )
        return orders

    @staticmethod
    def match_order(order: CustomerOrder, dealer_ask_price: float) -> CustomerOrder:
        """Fill the order if the dealer's ask is at or below the customer's WTP."""
        if dealer_ask_price <= order.willingness_to_pay:
            order.filled = True
            order.fill_price = dealer_ask_price
        else:
            order.filled = False
        return order
