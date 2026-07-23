"""
demand.py
=========

Phase 1 deliverable: Basic Customer Order Flow.

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

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Without customer arrivals, the dealer never sells anything: there is no
revenue, no inventory depletion, and no way to differentiate policies. The
whole point of a market-making simulation is quote-dependent trade execution,
which lives here.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class DemandParams:
    arrival_rate_per_year: float = 250.0   # avg customers/year, judgment call (Phase 0 register)
    order_size_mean_kg: float = 25.0       # mean order size (lognormal), judgment call
    order_size_sigma: float = 0.6          # lognormal shape parameter (right skew)
    wtp_spread_frac: float = 0.05          # customer WTP dispersion as fraction of mid price
    dt: float = 1.0 / 252.0


@dataclass
class CustomerOrder:
    size_kg: float
    willingness_to_pay: float
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
            orders.append(CustomerOrder(size_kg=float(size), willingness_to_pay=float(wtp)))
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
