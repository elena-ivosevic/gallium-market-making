"""
policies/avellaneda_stoikov.py
==============================

Phase 2 deliverable: a faithful reproduction of the standard Avellaneda-Stoikov
(2008) inventory-aware market-making model, before any physical-commodity
adjustments (those are Phase 5).

MODEL
-----
Reservation price (the price at which the dealer is indifferent to holding
current inventory, adjusted for risk):

    r(s, t) = s - q * gamma * sigma^2 * (T - t)

Optimal total spread (bid-ask width):

    delta = gamma * sigma^2 * (T - t) + (2 / gamma) * ln(1 + gamma / k)

Optimal quotes:

    ask = r(s, t) + delta / 2
    bid = r(s, t) - delta / 2

where:
    s      : current mid price
    q      : dealer's current inventory position (kg)
    gamma  : risk-aversion coefficient (register Section 5, "Risk-aversion
             coefficient (gamma)")
    sigma  : instantaneous ABSOLUTE price volatility (dollars), not the
             fractional/multiplicative volatility used in price_process.py
             -- see "Sigma unit conversion" below
    T - t  : time remaining until the trading horizon, in years
    k      : order-arrival sensitivity (register Section 5, "Order-arrival
             sensitivity parameter (k)") -- governs how fast a customer's
             fill probability decays as the quote moves away from a
             reference price, under the model's assumed
             lambda(delta) = A * exp(-k * delta) arrival intensity

WHY INVENTORY ENTERS THE RESERVATION PRICE
--------------------------------------------
A dealer holding physical inventory is exposed to price risk on that
inventory. The reservation price is not "the market price" -- it is the
price at which the dealer, given their current position, is indifferent
between holding and not holding one more unit. Carrying MORE inventory (q
large and positive) means more downside risk if the price falls, so the
dealer's true indifference point sits BELOW the mid price (they'd rather
sell some of it even at a discount) -- hence the minus sign: r = s - q * (...).
Carrying too LITTLE inventory has the opposite effect on the register's
"Available inventory" logic (Phase 3), but within the plain Avellaneda-
Stoikov reproduction here, only excess inventory is penalized by construction
(q enters linearly, with no floor/ceiling asymmetry yet -- that asymmetric
scarcity behavior is explicitly Phase 5's job, not this module's).

WHY RISK AVERSION (gamma) STRENGTHENS THE ADJUSTMENT
-------------------------------------------------------
gamma multiplies the entire inventory-risk term, q * gamma * sigma^2 * (T-t).
A more risk-averse dealer (higher gamma) demands a bigger price concession
for every unit of inventory risk carried -- the same q and the same sigma
produce a larger reservation-price shift when gamma is larger. This is a
direct, mechanical consequence of the formula, not a separate assumption.

WHY THE ADJUSTMENT SHRINKS NEAR THE END OF THE TRADING HORIZON
------------------------------------------------------------------
Both the reservation-price shift and the first term of the spread scale with
(T - t), the time remaining. As t -> T, (T - t) -> 0, so the inventory-risk
term vanishes and the reservation price converges back to the mid price --
holding inventory near the end of the horizon carries less *future* price
risk simply because there is less future left to be exposed to. The spread
does not fully collapse to zero, though: the second term,
(2/gamma) * ln(1 + gamma/k), reflects order-flow/adverse-selection
compensation that is independent of time remaining and persists even at
t = T.

SIGMA UNIT CONVERSION (an explicit adaptation, not a hidden assumption)
--------------------------------------------------------------------------
price_process.py's `sigma` is a fractional/multiplicative volatility (used
as sigma * S_t * dW in a mean-reverting SDE), whereas the classical
Avellaneda-Stoikov derivation assumes a simple arithmetic Brownian motion
with a constant ABSOLUTE volatility. This module converts by evaluating
`sigma_abs = sigma_frac * mid_price` at each call -- i.e., treating the
diffusion's instantaneous absolute volatility at the current price level as
the AS model's constant sigma. This is a reasonable local approximation, not
an exact match to the underlying mean-reverting jump-diffusion (which also
has jumps and mean reversion that the plain AS derivation does not account
for at all). Treat any "faithful reproduction" claim in this module as
scoped to the reservation-price/spread formulas themselves, not as a claim
that AS's assumptions perfectly describe price_process.py's SDE.

WHY THIS RESERVATION-PRICE / SPREAD PAIR AND NOT SOMETHING ELSE
--------------------------------------------------------------------
This is the standard, closed-form result from Avellaneda & Stoikov (2008),
"High-frequency trading in a limit order book," chosen as the project's
principled quoting baseline (register phase0_research_notes.md, Section 5)
specifically because it is the well-understood, citable starting point that
every later inventory/scarcity extension in this project (Phase 5) is built
by modifying, rather than a from-scratch design.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Inventory q enters as raw kilograms, not centered on a target/safety-stock
  level -- this is deliberate fidelity to the original paper's formula, not
  an oversight, but it means "zero inventory" (not "safety-stock-level
  inventory") is the reservation-price-neutral point in THIS module. Phase 5
  recenters this around available/target inventory.
- The order-arrival intensity this formula assumes, lambda(delta) =
  A * exp(-k * delta), is NOT the same execution model src/demand.py
  actually uses (a hard WTP threshold). k is calibrated as a judgment call
  to produce a plausible spread magnitude (see docs/assumptions_register.md,
  Section 8), not fitted to src/demand.py's actual fill-probability shape.
  This mismatch is real and is flagged for Phase 9 sensitivity testing.
- gamma and k are both judgment calls (register: "Academic-model assumption",
  Sensitivity: High) -- there is no gallium-dealer-specific estimate for
  either, by design (see docs/README_honesty_paragraph.md).
- The restock markup (`restock_markup_frac`) is the same Phase 1 supplier-
  procurement-premium stand-in used by the fixed-spread baseline -- this
  module does not yet use its own bid quote for restocking (that would
  require a genuine customer-facing bid side, which Phase 1's demand model
  does not support -- see policies/fixed_spread.py for the same note).

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
There is no inventory-aware quoting policy to compare the fixed-spread
baseline and the inventory-threshold heuristic against, and no principled
foundation for Phase 5's scarcity-adjusted policy to extend.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class AvellanedaStoikovParams:
    risk_aversion: float = 3.5e-6  # register Section 5, "Risk-aversion coefficient
                                    # (gamma)" -- judgment call, tuned (see
                                    # docs/assumptions_register.md Section 8) so that
                                    # a ~200 kg inventory position produces a
                                    # reservation-price shift on the order of a few
                                    # percent of price, not an unrealistic multiple of it
    k: float = 0.2                 # register Section 5, "Order-arrival sensitivity
                                    # parameter (k)" -- judgment call, tuned so the
                                    # order-flow spread term is a comparable magnitude
                                    # to the fixed-spread baseline's markup
    restock_markup_frac: float = 0.03  # same Phase 1 supplier-procurement-premium
                                    # stand-in as FixedSpreadParams.bid_markup_frac


class AvellanedaStoikovPolicy:
    """Standard inventory-aware market-making policy (Avellaneda & Stoikov, 2008)."""

    def __init__(self, params: AvellanedaStoikovParams):
        self.p = params
        if params.risk_aversion <= 0:
            raise ValueError("risk_aversion (gamma) must be positive")
        if params.k <= 0:
            raise ValueError("k must be positive")
        self.last_diagnostics: dict = {}

    def _compute_quotes(self, mid_price: float, inventory_kg: float,
                          t: float, T: float, sigma: float):
        gamma = self.p.risk_aversion
        k = self.p.k
        time_remaining = max(T - t, 0.0)
        sigma_abs = sigma * mid_price  # see "Sigma unit conversion" in module docstring

        reservation_price = mid_price - inventory_kg * gamma * (sigma_abs ** 2) * time_remaining
        spread = gamma * (sigma_abs ** 2) * time_remaining + (2.0 / gamma) * np.log(1.0 + gamma / k)
        ask = reservation_price + spread / 2.0
        bid = reservation_price - spread / 2.0
        return reservation_price, bid, ask, spread, time_remaining

    def quote_ask(self, mid_price: float, inventory_kg: float = 0.0,
                   avg_cost_basis: float = 0.0, t: float = 0.0, T: float = 1.0,
                   sigma: float = 0.35, **_ignored_state) -> float:
        """
        Return the ask price. `t`, `T` (years), and `sigma` (fractional,
        as used in price_process.py) are supplied by the simulation loop;
        `**_ignored_state` absorbs anything this policy doesn't use, matching
        the shared policy interface (see src/simulation.py).
        """
        reservation_price, bid, ask, spread, time_remaining = self._compute_quotes(
            mid_price, inventory_kg, t, T, sigma
        )
        self.last_diagnostics = {
            "mid_price": mid_price,
            "reservation_price": reservation_price,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "inventory_kg": inventory_kg,
            "time_remaining": time_remaining,
        }
        return ask

    def restock_markup_frac(self, **_ignored_state) -> float:
        """See module docstring, 'Limitations', for why this is a flagged
        stand-in rather than a genuine customer-facing bid."""
        return self.p.restock_markup_frac
