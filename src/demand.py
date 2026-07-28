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
    sector: str = "aggregate"  # (Phase 4) which sector this order came from;
                                # "aggregate" for all Phase 1-3 orders (pre-sector)
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


# =============================================================================
# Phase 4 deliverable: Sector-Specific Customers + Hawkes Demand Process +
# Military Demand Price-Sensitivity.
#
# Everything above this line (DemandParams, CustomerOrder, PoissonOrderFlow) is
# UNCHANGED from Phase 1-3 and remains fully functional for backward
# compatibility -- every earlier test still exercises exactly that code path.
# SectorHawkesOrderFlow below is a new, separate, opt-in class; nothing above
# calls into it and nothing below is called by Phase 1-3 code.
# =============================================================================

"""
WHY SECTORS, NOT ONE HOMOGENEOUS DEMAND POOL
------------------------------------------------
Phase 1 deliberately kept demand homogeneous ("Sector and end-use
distinctions ... are deliberately deferred to Phase 4 -- keep this phase
homogeneous"). Real gallium demand is not homogeneous: semiconductor demand
is high-volume and relatively price-sensitive, Defense & Aerospace demand is
low-volume but high-value and much less price-sensitive, and so on
(docs/phase0_research_notes.md, Section 3). Four sectors are modeled here --
Semiconductors, Telecommunications, Defense & Aerospace, Solar/Clean Energy
-- with independently calibrated arrival rate, order size, WTP dispersion,
and military-linked share (docs/assumptions_register.md, Section 11.4).

WHY A HAWKES PROCESS INSTEAD OF JUST A HIGHER POISSON RATE DURING SEVERE
------------------------------------------------------------------------------
A regime-dependent Poisson rate (see src/regimes.py's
`demand_intensity_multiplier`) captures "more orders arrive on average during
a disruption," but it can't capture CLUSTERING -- one urgent order raising
the near-term probability of more urgent orders, the way real panic buying
behaves (docs/phase0_research_notes.md, Section 5, Mastery Checkpoint Q2).
This module layers a Hawkes-style self-exciting term on top of the
regime-modulated Poisson base rate: every arriving order temporarily raises
a shared "excitation" state, which decays exponentially
(docs/assumptions_register.md, Section 11.7) and adds directly to the
following days' arrival intensity.

A DELIBERATE SIMPLIFICATION: ONE SHARED EXCITATION STATE, NOT FOUR
------------------------------------------------------------------------
A fully faithful per-sector Hawkes process would give each of the four
sectors its own excitation state, evolving independently. This module
instead maintains a SINGLE, market-wide excitation state, distributed across
sectors in proportion to each sector's base arrival rate. This is a
deliberate simplification (a "market-wide panic signal" rather than
sector-siloed panic), chosen because there is no data suggesting sector-level
panic clustering happens independently rather than as a shared market
reaction to the same disruption news -- and because four independent Hawkes
states would quadruple the untestable free parameters for no evidenced
benefit. Flagged here, not hidden.

WHY MILITARY-LINKED ORDERS GET A WIDER, SHIFTED WTP DISTRIBUTION
------------------------------------------------------------------
This is the register's previously-flagged gap (Section 10: "Without a
price-sensitivity difference, a pricing-only policy has no way to
differentially protect military demand through the ask price alone").
Military-linked orders draw willingness-to-pay from a distribution that is
BOTH wider (register Section 11.6: 2.5x the civilian spread -- a flatter
execution-probability-vs-price curve, i.e. less likely to walk away as price
rises) AND shifted higher (+3% mean) than civilian orders in the same
sector. This does not change which policy a dealer runs -- it changes
whether tagging an order "military-linked" does anything at all to
simulated outcomes under a pricing-only policy, which is exactly this
project's mastery-checkpoint question from Phase 0.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Shared (not per-sector) Hawkes excitation, as above.
- Military elasticity parameters (2.5x spread, +3% mean shift) are judgment
  calls with no fitted procurement data behind them -- register Section 11.6,
  flagged for Phase 9 sensitivity.
- Sector definitions are still relatively coarse (four sectors, each
  internally homogeneous) -- no within-sector customer heterogeneity.
- Order size distribution shape (lognormal, sigma reused from Phase 1's
  DemandParams default) is not re-calibrated per sector beyond the mean.

WHAT BREAKS IF THIS CLASS IS REMOVED
--------------------------------------
Phase 4's regime-switching supply chain would have nothing but flat,
homogeneous demand to react to -- there would be no sector-level fill-rate
comparison (needed for Phase 7), no demand clustering to stress-test
inventory against (needed for the Hawkes ablation in Phase 9), and no way to
observe whether military-linked demand's price-INsensitivity alone changes
outcomes under a pricing-only policy (this project's central open question).
"""

@dataclass
class SectorParams:
    name: str
    arrival_rate_per_year: float
    order_size_mean_kg: float
    wtp_spread_frac: float
    military_linked_share: float
    order_size_sigma: float = 0.6  # reused from Phase 1's DemandParams default


# Register Section 11.4
DEFAULT_SECTORS: list[SectorParams] = [
    SectorParams("semiconductors", arrival_rate_per_year=140.0, order_size_mean_kg=20.0,
                 wtp_spread_frac=0.04, military_linked_share=0.10),
    SectorParams("telecommunications", arrival_rate_per_year=70.0, order_size_mean_kg=22.0,
                 wtp_spread_frac=0.045, military_linked_share=0.12),
    SectorParams("defense_aerospace", arrival_rate_per_year=25.0, order_size_mean_kg=35.0,
                 wtp_spread_frac=0.08, military_linked_share=0.70),
    SectorParams("solar_clean_energy", arrival_rate_per_year=40.0, order_size_mean_kg=18.0,
                 wtp_spread_frac=0.06, military_linked_share=0.05),
]


@dataclass
class MilitaryElasticityParams:
    wtp_spread_multiplier: float = 2.5   # register Section 11.6
    wtp_mean_shift_frac: float = 0.03    # register Section 11.6


@dataclass
class HawkesParams:
    decay_rate_per_year: float = 8.0     # register Section 11.7 (~32-day half-life)


class SectorHawkesOrderFlow:
    """
    Phase 4 order flow: per-sector Poisson base rates, regime-modulated,
    plus a shared Hawkes excitation term for clustering, plus military-linked
    tagging with elasticity-adjusted willingness-to-pay. See module docstring
    above for the full rationale and the "one shared excitation state"
    simplification.
    """

    def __init__(
        self,
        sectors: list[SectorParams] | None = None,
        military_elasticity: MilitaryElasticityParams | None = None,
        hawkes_params: HawkesParams | None = None,
        seed: int | None = None,
    ):
        self.sectors = sectors if sectors is not None else DEFAULT_SECTORS
        self.military_elasticity = military_elasticity or MilitaryElasticityParams()
        self.hawkes = hawkes_params or HawkesParams()
        self.rng = np.random.default_rng(seed)
        self.excitation = 0.0
        self._total_base_rate = sum(s.arrival_rate_per_year for s in self.sectors)
        self.excitation_history: list[float] = []

    def generate_orders(
        self,
        mid_price: float,
        dt: float,
        demand_intensity_multiplier: float = 1.0,
        hawkes_excitation_strength: float = 0.05,
    ) -> list[CustomerOrder]:
        """
        One simulated day of order arrivals across all sectors.

        `demand_intensity_multiplier` and `hawkes_excitation_strength` are
        supplied by the caller (src/simulation.py, from the current
        RegimeSwitcher state) -- this class has no notion of regimes itself,
        matching this project's established pattern of policies/order-flow
        never reaching into another module's internal state (see
        src/simulation.py's generic diagnostics hook, Phase 2).
        """
        # Decay yesterday's excitation before this day's arrivals contribute
        # new excitation -- order matters: decay first, then add.
        self.excitation *= np.exp(-self.hawkes.decay_rate_per_year * dt)

        orders: list[CustomerOrder] = []
        for sector in self.sectors:
            # This sector's share of the shared excitation term, in
            # proportion to its base arrival rate (see "one shared
            # excitation state" in the module docstring).
            sector_share = sector.arrival_rate_per_year / self._total_base_rate
            lam = (
                sector.arrival_rate_per_year * demand_intensity_multiplier
                + self.excitation * sector_share
            ) * dt
            n_orders = self.rng.poisson(max(lam, 0.0))

            for _ in range(n_orders):
                size = self.rng.lognormal(
                    mean=np.log(sector.order_size_mean_kg) - 0.5 * sector.order_size_sigma**2,
                    sigma=sector.order_size_sigma,
                )
                military_linked = bool(self.rng.random() < sector.military_linked_share)

                spread = sector.wtp_spread_frac
                mean_shift = 0.0
                if military_linked:
                    spread = spread * self.military_elasticity.wtp_spread_multiplier
                    mean_shift = self.military_elasticity.wtp_mean_shift_frac
                wtp = mid_price * (1.0 + mean_shift + self.rng.normal(0.0, spread))

                orders.append(
                    CustomerOrder(
                        size_kg=float(size),
                        willingness_to_pay=float(wtp),
                        military_linked=military_linked,
                        sector=sector.name,
                    )
                )
                # Each arriving order raises the shared excitation state --
                # standard Hawkes self-excitation, applied once per event.
                self.excitation += hawkes_excitation_strength

        self.excitation_history.append(self.excitation)
        return orders
