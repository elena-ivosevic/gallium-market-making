"""
policies/inventory_heuristic.py
================================

Phase 2 deliverable: Inventory-threshold heuristic, the comparison point the
roadmap explicitly asks for alongside the fixed-spread baseline when
evaluating the standard Avellaneda-Stoikov policy.

MODEL
-----
A step function on inventory level, not a continuous adjustment:

    if inventory_kg <= low_threshold_kg:  ask = mid * (1 + base_ask_spread_frac
                                                          + low_inventory_extra_frac)
    elif inventory_kg >= high_threshold_kg: ask = mid * (1 + base_ask_spread_frac
                                                            - high_inventory_discount_frac)
    else:                                   ask = mid * (1 + base_ask_spread_frac)

WHY THIS EXISTS
----------------
This is the natural thing a dealer without any formal quantitative model
might actually do: "if we're getting low, charge more; if we're overstocked,
discount to move product; otherwise, charge the normal markup." It captures
SOME inventory awareness (unlike the fixed-spread baseline) without any of
the theoretical structure of Avellaneda-Stoikov (no risk-aversion parameter,
no time-horizon decay, no continuous adjustment). Comparing standard AS
against BOTH this heuristic and the pure fixed-spread baseline is what lets
Phase 2 make a meaningful claim about whether the formal model's added
structure is earning its complexity, rather than just beating the dumbest
possible strategy.

WHY A STEP FUNCTION RATHER THAN A CONTINUOUS RULE
------------------------------------------------------
The whole point of including this policy is that it represents a
qualitatively different, less sophisticated design choice than Avellaneda-
Stoikov's continuous, theoretically-derived adjustment. A continuous
"linear in inventory" heuristic would just be a crude approximation of AS's
own inventory term; the discrete threshold rule is a genuinely different
strategy shape, which makes for a more informative comparison.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- No risk-aversion parameter, no time-horizon awareness, no volatility
  awareness at all -- the adjustment magnitude and thresholds are fixed
  constants, not derived from anything.
- Discontinuous: an inventory move of a single kg across a threshold causes
  a sudden jump in quoted price, which is a known weakness of any bang-bang
  threshold rule (a real dealer's customers might notice and react to that
  discontinuity in ways this simulation does not model).
- Threshold levels and adjustment sizes (`low_threshold_kg`,
  `high_threshold_kg`, `low_inventory_extra_frac`,
  `high_inventory_discount_frac`) are judgment calls with no register row
  prior to this Phase 2 pass -- logged in docs/assumptions_register.md,
  Section 8, per this project's rule that no parameter is added to code
  before it has a row there.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Phase 2's comparison would only be "fixed-spread vs. standard AS," losing
the roadmap-required middle comparison point that shows whether AS's benefit
(if any) comes from being inventory-aware at all, or specifically from its
continuous, theoretically-grounded adjustment shape.
"""

from dataclasses import dataclass


@dataclass
class InventoryHeuristicParams:
    base_ask_spread_frac: float = 0.04       # same magnitude as the fixed-spread
                                              # baseline's ask_spread_frac, so any
                                              # difference in outcomes is attributable
                                              # to the inventory-awareness logic, not
                                              # a different baseline markup
    low_threshold_kg: float = 80.0           # at/below this, treat inventory as scarce
    high_threshold_kg: float = 250.0         # at/above this, treat inventory as excess
    low_inventory_extra_frac: float = 0.03   # extra ask markup when scarce
    high_inventory_discount_frac: float = 0.02  # ask discount when excess
    restock_markup_frac: float = 0.03        # same Phase 1 supplier-procurement-premium
                                              # stand-in as the other Phase 1/2 policies


class InventoryHeuristicPolicy:
    """Step-function inventory awareness: charge more when scarce, less when flush."""

    def __init__(self, params: InventoryHeuristicParams):
        self.p = params
        self.last_diagnostics: dict = {}

    def quote_ask(self, mid_price: float, inventory_kg: float = 0.0,
                   avg_cost_basis: float = 0.0, **_ignored_state) -> float:
        p = self.p
        if inventory_kg <= p.low_threshold_kg:
            spread_frac = p.base_ask_spread_frac + p.low_inventory_extra_frac
            regime = "scarce"
        elif inventory_kg >= p.high_threshold_kg:
            spread_frac = p.base_ask_spread_frac - p.high_inventory_discount_frac
            regime = "excess"
        else:
            spread_frac = p.base_ask_spread_frac
            regime = "normal"

        ask = mid_price * (1.0 + spread_frac)
        self.last_diagnostics = {
            "mid_price": mid_price,
            "ask": ask,
            "spread_frac": spread_frac,
            "inventory_kg": inventory_kg,
            "inventory_regime": regime,
        }
        return ask

    def restock_markup_frac(self, **_ignored_state) -> float:
        return self.p.restock_markup_frac
