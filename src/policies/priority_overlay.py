"""
policies/priority_overlay.py
=============================

Phase 5 deliverable: Priority-Allocation Overlay -- a DPAS-style ("rated
order") non-price mechanism, modeled on Defense Production Act Title I
priority allocation. Unlike every other policy in this project, this is NOT
a pricing model: it never touches a quote. It is a modifier that can be
layered on top of ANY policy's fill sequence.

WHAT THIS MODULE DOES
----------------------
When more than one order arrives on the same simulated day, and at least
one is military-linked and at least one is civilian, this overlay decides
-- with probability `p` -- whether military-linked orders are attempted
FIRST that day, ahead of civilian orders, when competing for the same
limited physical inventory. At `p = 0` this never happens (today's
arrival-order default). At `p = 1` it always happens (a hard mandate). This
directly implements the roadmap's own specification: "one continuous
strictness parameter... p=0 is no overlay... p=1 is the hard DPAS-style
mandate... values in between mean the military order wins the priority
draw with probability p."

WHY THIS IS REACTIVE, NOT PROACTIVE
----------------------------------------
The overlay never causes the dealer to hold extra safety stock in advance
"just in case" a military order might arrive later -- that would blend the
overlay into inventory-risk logic (Phase 5's scarcity premium already does
that) and make the "pricing alone vs. pricing + mandate" comparison murkier
than it needs to be. Quoting happens EXACTLY the same way whether the
overlay is on or off (this class never calls a policy's `quote_ask`, and no
policy is aware this class exists); only the FILL ATTEMPT SEQUENCE on
contested days differs. See docs/assumptions_register.md, Section 12.2, for
why "contested" is scoped to same-day arrivals in this project's discrete
daily-timestep architecture, rather than the roadmap's more general
continuous-time framing.

WHY A SINGLE DAY-LEVEL BERNOULLI DRAW, NOT A PER-ORDER-PAIR DRAW
------------------------------------------------------------------------
With this project's calibrated arrival rates (a few hundred orders per
year), most days have zero or one order; genuine multi-order contention is
relatively rare outside Hawkes-clustered panic periods (Phase 4) -- which is
exactly when the overlay matters most. A single draw per contested day
(rather than a separate draw for every possible pair of orders) is a
simplification of the roadmap's continuous-time language, logged explicitly
here rather than silently assumed to be equivalent.

WHY p IS A SINGLE CONTINUOUS PARAMETER, NOT A BINARY FLAG
------------------------------------------------------------
This one parameter serves BOTH the headline ablation (Phase 9: p=0 vs p=1)
and the sensitivity sweep (Phase 9: sweep p continuously) without needing
two different code paths -- directly per the roadmap's own design rationale
for this parameter.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Day-level, not pairwise, contention resolution (see above).
- Does not implement DPAS's two-tier system (DX above DO, both above
  unrated) -- a single continuous p is used instead, per the roadmap's own
  note that this is "enough to answer the core research question."
- Reordering the day's fill attempts can change which orders backorder vs.
  get an emergency order vs. (for civilian orders) get rejected outright --
  this is the INTENDED mechanism, not a side effect, but it means overlay
  strictness has ripple effects on stockout_events and emergency-order
  counts that Phase 9's ablation should examine explicitly, not just the
  fill-rate gap.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
There would be no way to isolate whether price-based scarcity adjustment
(Phase 5's ScarcityAdjustedASPolicy) alone is sufficient to protect
military-critical supply, or whether it takes an explicit, non-price
mandate -- this project's second core research question would have no
mechanism to test the "mandate" side of "price vs. mandate."
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class PriorityOverlayParams:
    p: float = 1.0  # register Section 12.2 -- strictness, 0 (off) to 1 (hard mandate)

    def __post_init__(self):
        if not (0.0 <= self.p <= 1.0):
            raise ValueError("p must be in [0, 1]")


class PriorityOverlay:
    """Reorders a day's want-to-fill orders so military-linked orders are
    attempted first with probability p, only on days where both civilian
    and military-linked orders are actually competing. Never touches a
    price. See module docstring for the full rationale."""

    def __init__(self, params: PriorityOverlayParams, seed: int | None = None):
        self.p = params
        self.rng = np.random.default_rng(seed)
        self.contested_days = 0
        self.days_military_prioritized = 0

    def order_sequence(self, orders: list) -> list:
        """
        Given today's want-to-fill orders (in original arrival order),
        return a possibly-reordered list. Orders within each channel keep
        their relative arrival order (this only ever reorders ACROSS
        channels, never within one).
        """
        if len(orders) <= 1:
            return orders

        military = [o for o in orders if o.military_linked]
        civilian = [o for o in orders if not o.military_linked]
        if not military or not civilian:
            return orders  # nothing contested today -- only one channel present

        # Contention is counted regardless of p, so diagnostics reflect how
        # often genuine cross-channel contention occurred, even at p=0
        # (where the overlay never actually reorders).
        self.contested_days += 1
        if self.p.p <= 0.0:
            return orders
        if self.rng.random() < self.p.p:
            self.days_military_prioritized += 1
            return military + civilian
        return orders
