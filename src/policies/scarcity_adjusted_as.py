"""
policies/scarcity_adjusted_as.py
=================================

Phase 5 deliverable: the project's MAIN model. Extends the standard
Avellaneda-Stoikov reservation price (Phase 2) with five additive premiums
that react to physical-market conditions a financial market-making model
has no notion of: scarcity, replacement cost, shipment risk, standing
commitments, and regime severity.

MODEL
-----
    reservation_price_scarcity_adjusted =
        AS_reservation_price
        + scarcity_premium
        + replacement_cost_premium
        + shipment_risk_premium
        + commitment_premium
        + regime_premium

    ask = reservation_price_scarcity_adjusted + spread/2   (spread: unchanged AS formula)

Each premium is a non-negative dollar amount (never negative -- these only
ever push the ask UP, protecting inventory, never down). See
docs/assumptions_register.md, Section 12.1, for the exact formula, capping,
and parameter value for each.

WHY FIVE SEPARATE PREMIUMS, NOT ONE COMBINED "SCARCITY SCORE"
-------------------------------------------------------------------
Each premium reacts to a DIFFERENT physical-market signal that can move
independently of the others:
  - scarcity: how close available inventory is to the safety-stock floor
  - replacement cost: how expensive restocking is right now (already
    computed by supply_chain.py for the dealer's own purchases -- this
    premium partially passes that same signal through to customer quotes)
  - shipment risk: how reliable the CURRENT supply channel is
  - commitment: how much inventory is already owed to (military-linked)
    backorders and therefore not really "available" to a new customer
  - regime: a direct, bounded signal for how severe the current disruption
    is, independent of the other four (which each already react to regime
    indirectly, through reliability and scarcity)
Collapsing these into one number would make Phase 9's ablation
uninformative -- "remove the scarcity premium" and "remove the regime
premium" need to be independently testable, per the roadmap's own
pre-registered ablation table (register Section 12.3).

WHY EVERY RATIO-BASED TERM IS EXPLICITLY CAPPED
------------------------------------------------------
Phase 3's supply_chain.py once let a shortfall ratio grow without bound,
producing markups over 60,000% and a -$5.6M simulated result before being
caught and fixed (register Section 9). Every premium here that divides by a
potentially-small denominator (safety_stock_kg) is capped BEFORE being
squared or otherwise amplified, so the worst case is severe but bounded,
not runaway.

WHY THESE PREMIUMS ONLY RAISE THE RESERVATION PRICE, NOT THE SPREAD WIDTH DIRECTLY
--------------------------------------------------------------------------------------
The standard AS spread formula (`delta = gamma*sigma^2*(T-t) + (2/gamma)*ln(1+gamma/k)`)
is left completely unchanged. Raising the reservation price still raises the
ask directly (`ask = r + delta/2`), which is where a customer actually feels
the scarcity protection -- there is no separate customer-facing bid in this
project's demand model (see policies/fixed_spread.py's docstring for why),
so widening the spread's own formula would only ever affect an unused bid
side. This is a deliberate simplification, not an oversight.

WHY REPLACEMENT-COST PASS-THROUGH IS PARTIAL (15%), NOT FULL
------------------------------------------------------------------
supply_chain.py's own `replacement_markup_frac` can reach 203% of price in
the worst case (register Section 9) -- passing that fully through to every
customer quote would make the dealer's ask economically absurd during any
real scarcity event. `replacement_cost_pass_through = 0.15` reflects that a
dealer eats some of its own restocking cost rather than passing all of it
on, which is both more realistic and keeps the combined premium bounded to
a "severe but not absurd" ~62% worst case (register Section 12.1).

LIMITATIONS (explicit, not hidden)
-----------------------------------
- All five gamma coefficients are judgment calls with no fitted data behind
  them -- register Section 12.1, all flagged for Phase 9's sweep.
- Premiums only raise the ask; there is still no genuine customer-facing bid
  for them to widen symmetrically (see Phase 1/2's flagged limitation,
  unchanged).
- The regime premium and the other four premiums are not fully independent
  in practice (shipment-risk and scarcity both react to the same underlying
  regime, just through different channels) -- Phase 9's ablation is exactly
  what should quantify how much unique information the regime premium adds
  on top of the other four, not this module.
- `civilian_reliability`, `available_kg`, `committed_kg`, `regime_severity`,
  etc. are all optional kwargs supplied by the simulation loop; when this
  policy is run OUTSIDE supply-chain/regime mode (i.e., with just Phase 1/2
  state), every premium silently evaluates to its floor (zero, or the flat
  replacement_cost_pass_through baseline) -- this policy degrades gracefully
  to something close to plain AS rather than erroring, but that also means
  it is not meaningfully different from Phase 2's AS policy outside Phase
  3/4 mode, which is expected, not a bug.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
There would be no policy embodying this project's core hypothesis (does a
principled, physical-market-aware quoting policy outperform naive
heuristics under supply disruption?) -- Phase 2's plain AS has no notion of
scarcity, replacement cost, shipment risk, commitments, or regime at all.
"""

from dataclasses import dataclass
import numpy as np

from src.policies.avellaneda_stoikov import AvellanedaStoikovPolicy, AvellanedaStoikovParams


@dataclass
class ScarcityAdjustedASParams(AvellanedaStoikovParams):
    scarcity_gamma: float = 0.05                    # register Section 12.1
    replacement_cost_pass_through: float = 0.15      # register Section 12.1
    shipment_risk_gamma: float = 0.10                # register Section 12.1
    commitment_gamma: float = 0.03                   # register Section 12.1
    regime_gamma: float = 0.08                       # register Section 12.1
    replacement_cost_base_markup: float = 0.03       # matches supply_chain.py's own default,
                                                      # used only to compute the EXCESS portion
                                                      # of replacement_markup_frac (see below)


class ScarcityAdjustedASPolicy(AvellanedaStoikovPolicy):
    """Standard AS reservation price/spread, plus five bounded, additive
    physical-market premiums. See module docstring for the full model."""

    def __init__(self, params: ScarcityAdjustedASParams):
        super().__init__(params)  # validates gamma/k via the parent class
        self.p: ScarcityAdjustedASParams = params

    def _compute_premiums(
        self,
        mid_price: float,
        available_kg: float | None,
        safety_stock_kg: float | None,
        replacement_markup_frac: float | None,
        civilian_reliability: float | None,
        committed_kg: float,
        regime_severity: float,
    ) -> dict:
        p = self.p

        # Scarcity premium -- register Section 12.1. Capped shortfall ratio,
        # same lesson as Section 9's replacement-cost fix.
        if available_kg is not None and safety_stock_kg is not None and safety_stock_kg > 0:
            shortfall = max(0.0, safety_stock_kg - available_kg)
            shortfall_ratio = min(1.0, shortfall / safety_stock_kg)
        else:
            shortfall_ratio = 0.0
        scarcity_premium = mid_price * p.scarcity_gamma * (shortfall_ratio ** 2)

        # Replacement-cost premium -- only the EXCESS above the flat base
        # markup is passed through, and only partially (pass_through < 1).
        if replacement_markup_frac is not None:
            excess = max(0.0, replacement_markup_frac - p.replacement_cost_base_markup)
        else:
            excess = 0.0
        replacement_cost_premium = mid_price * p.replacement_cost_pass_through * excess

        # Shipment-risk premium -- reacts to CURRENT civilian reliability
        # directly (already regime-modulated upstream, if regime mode is on).
        reliability = civilian_reliability if civilian_reliability is not None else 1.0
        shipment_risk_premium = mid_price * p.shipment_risk_gamma * max(0.0, 1.0 - reliability)

        # Commitment premium -- capped at 3x safety stock's worth of backlog.
        if safety_stock_kg is not None and safety_stock_kg > 0:
            commitment_ratio = min(3.0, committed_kg / safety_stock_kg)
        else:
            commitment_ratio = 0.0
        commitment_premium = mid_price * p.commitment_gamma * commitment_ratio

        # Regime premium -- regime_severity is pre-clamped to [0, 1] by the caller.
        regime_premium = mid_price * p.regime_gamma * max(0.0, min(1.0, regime_severity))

        return {
            "scarcity_premium": scarcity_premium,
            "replacement_cost_premium": replacement_cost_premium,
            "shipment_risk_premium": shipment_risk_premium,
            "commitment_premium": commitment_premium,
            "regime_premium": regime_premium,
            "total_premium": (
                scarcity_premium + replacement_cost_premium + shipment_risk_premium
                + commitment_premium + regime_premium
            ),
        }

    def quote_ask(
        self,
        mid_price: float,
        inventory_kg: float = 0.0,
        avg_cost_basis: float = 0.0,
        t: float = 0.0,
        T: float = 1.0,
        sigma: float = 0.35,
        available_kg: float | None = None,
        safety_stock_kg: float | None = None,
        replacement_markup_frac: float | None = None,
        civilian_reliability: float | None = None,
        committed_kg: float = 0.0,
        regime_severity: float = 0.0,
        **_ignored_state,
    ) -> float:
        """
        Extends AvellanedaStoikovPolicy.quote_ask with five physical-market
        premiums. All new kwargs are OPTIONAL and supplied by the simulation
        loop when Phase 3 (supply-chain) / Phase 4 (regime) mode is active;
        outside those modes every premium defaults to zero (or the flat
        baseline), and this policy behaves like plain AS -- see module
        docstring, "Limitations."
        """
        base_reservation, bid, base_ask, spread, time_remaining = self._compute_quotes(
            mid_price, inventory_kg, t, T, sigma
        )
        premiums = self._compute_premiums(
            mid_price, available_kg, safety_stock_kg, replacement_markup_frac,
            civilian_reliability, committed_kg, regime_severity,
        )
        reservation_price = base_reservation + premiums["total_premium"]
        ask = reservation_price + spread / 2.0
        bid = reservation_price - spread / 2.0

        self.last_diagnostics = {
            "mid_price": mid_price,
            "base_reservation_price": base_reservation,
            "reservation_price": reservation_price,
            "bid": bid,
            "ask": ask,
            "spread": spread,
            "inventory_kg": inventory_kg,
            "time_remaining": time_remaining,
            **premiums,
        }
        return ask
