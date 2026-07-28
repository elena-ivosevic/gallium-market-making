"""
policies/dynamic_programming.py
=================================

Phase 6 deliverable: a finite-state dynamic-programming policy, solved via
backward induction over a discretized (inventory bin, regime, day) state
space. Genuinely different in kind from every earlier policy in this
project: Avellaneda-Stoikov and its scarcity-adjusted extension (Phases 2,
5) compute a quote from a closed-form FORMULA at each moment; this policy
looks up a quote from a POLICY TABLE solved once, offline, at construction
time, by explicitly reasoning about the future value of every possible
state -- the same idea as the toy problem in dp_toy_example.py, just with
more states and actions.

THE FIVE ACTIONS (per the roadmap)
--------------------------------------
- Quote aggressively  -> 1% markup (high fill probability, low margin)
- Quote normally       -> 4% markup (matches other policies' baseline)
- Quote defensively    -> 10% markup (low fill probability, protects inventory)
- Stop selling         -> 100% markup (near-impossible to fill given any
                           realistic willingness-to-pay dispersion)
- Purchase emergency inventory -> quotes at the "normal" markup AND signals
  the simulation loop (via `wants_emergency_purchase()`) to place a real
  emergency order that day, regardless of the reorder-point logic Phase 3's
  supply chain otherwise uses on its own

WHY THIS POLICY NEEDS ITS OWN SIMPLIFIED INTERNAL WORLD MODEL
--------------------------------------------------------------------
Exact backward induction requires enumerating, for every state and action,
the full probability distribution over next states. The REAL simulation's
dynamics (jump-diffusion prices, Hawkes-clustered sector demand, partial
shipment failures, a five-premium scarcity-adjusted competitor policy
elsewhere in the market) have no closed form -- there is no way to write
down "P(next_state | state, action)" for the actual environment without
already having simulated it, which defeats the purpose of solving a policy
in advance. So this module builds its OWN small, explicit, closed-form
approximation of the world (register Section 13.1: 5 inventory bins x 4
regimes x N days, a simplified Bernoulli sale/restock model, a simplified
fill-probability formula) -- solves that exactly -- and then deploys the
resulting table against the real simulation. This gap between "the world
the policy was solved for" and "the world it actually runs in" is real and
is the central limitation of this whole approach; see the mastery
checkpoint in the README for why that's an inherent, not accidental,
property of finite-state DP.

WHY BACKWARD INDUCTION, NOT VALUE ITERATION
------------------------------------------------
This project's horizon is finite and known (the same `T = n_steps * dt`
Avellaneda-Stoikov uses, Phase 2) -- backward induction from a known
terminal condition is the natural, exact solution method for a finite
horizon, and avoids value iteration's need to check for convergence over
an indefinite number of sweeps.

WHY REGIME TRANSITIONS ARE REUSED DIRECTLY FROM regimes.py
------------------------------------------------------------------
The DP's own simplified world model still needs to know how regimes evolve.
Rather than inventing a second, DP-specific regime model (which would risk
silently disagreeing with the actual simulation's regime dynamics), this
policy reuses `RegimeParams().transition_matrix` (Phase 4) verbatim -- the
one piece of the DP's internal model that is NOT a simplification relative
to the real simulation.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- The DP's internal sale/restock/fill-probability model is a deliberate,
  documented simplification (register Section 13.1) -- see "why this policy
  needs its own simplified internal world model" above. It does not know
  about sectors, Hawkes clustering, military-linked demand, jump-diffusion
  prices, or any other policy competing in the same market.
- Inventory is discretized into 5 bins; within-bin inventory differences are
  invisible to the policy (a dealer at 61kg and a dealer at 119kg with a
  60kg-wide bin see the identical quote, if both fall in the same bin).
- The policy table is solved ONCE at construction, assuming a FIXED horizon
  (`n_steps`) and a FIXED `safety_stock_kg` (used to set bin edges) --
  constructing this policy with a different accounting configuration than
  the one it was solved for silently uses stale bin edges.
- `wants_emergency_purchase()` only signals intent; src/simulation.py
  decides whether/how to actually place the order (see its docstring for
  the hook's exact behavior).

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
There would be no policy in this project that explicitly reasons about the
FUTURE value of preserving inventory via an exact, verifiable optimization
(as opposed to Avellaneda-Stoikov's closed-form formula, which is optimal
under ITS OWN, different set of continuous-time assumptions) -- the
roadmap's Phase 6 goal ("a policy that explicitly considers both immediate
trading profit and future value of preserving inventory") would have no
concrete implementation to compare against Phase 5's scarcity-adjusted
policy.
"""

from dataclasses import dataclass, field
from scipy.stats import norm
import numpy as np

from src.regimes import RegimeParams, REGIMES

ACTIONS = ("aggressive", "normal", "defensive", "stop", "emergency_purchase")

ACTION_MARKUPS = {
    "aggressive": 0.01,
    "normal": 0.04,
    "defensive": 0.10,
    "stop": 1.00,
    "emergency_purchase": 0.04,
}


@dataclass
class DynamicProgrammingParams:
    n_inventory_bins: int = 5                          # register Section 13.1
    bin_edge_multipliers: tuple = (0.0, 0.5, 1.0, 2.0, 4.0)  # x safety_stock_kg
    wtp_spread_frac: float = 0.05                       # register Section 7, reused
    daily_restock_prob: float = 0.15                    # register Section 13.1
    scarcity_penalty: float = -5.0                      # register Section 13.1
    emergency_purchase_cost: float = -8.0                # register Section 13.1
    terminal_value_per_bin: float = 6.0                  # register Section 13.1
    reference_price: float = 350.0                       # DP's fixed internal price proxy
                                                          # (register Section 1's s0/theta) --
                                                          # the real simulation's price is
                                                          # stochastic; the DP cannot solve
                                                          # exactly against a moving target,
                                                          # so it plans against a fixed
                                                          # reference and re-quotes off the
                                                          # ACTUAL mid_price at runtime
    order_size_mean_kg: float = 25.0                     # register Section 7, reused
    regime_params: RegimeParams = field(default_factory=RegimeParams)


class DynamicProgrammingPolicy:
    """Finite-state DP policy: solves its own simplified world model via
    backward induction at construction time, then does O(1) table lookups
    at runtime. See module docstring for the full rationale."""

    def __init__(self, params: DynamicProgrammingParams, n_steps: int, safety_stock_kg: float):
        self.p = params
        self.n_steps = n_steps
        self.safety_stock_kg = safety_stock_kg
        self.bin_edges_kg = [m * safety_stock_kg for m in params.bin_edge_multipliers] + [np.inf]
        self._fill_prob_cache = {
            action: self._fill_probability(markup) for action, markup in ACTION_MARKUPS.items()
        }
        self.last_diagnostics: dict = {}
        self._solve()

    # ---- discretization helpers --------------------------------------------

    def _inventory_to_bin(self, inventory_kg: float) -> int:
        for i in range(self.p.n_inventory_bins):
            if inventory_kg < self.bin_edges_kg[i + 1]:
                return i
        return self.p.n_inventory_bins - 1

    def _fill_probability(self, markup_frac: float) -> float:
        """DP's own simplified fill-probability model (register Section
        13.1) -- P(customer's WTP >= ask), assuming WTP ~ Normal(mid,
        wtp_spread_frac * mid). Reuses the exact closed-form logic already
        used elsewhere in this project (e.g. Phase 1's demo-run sanity check)."""
        if self.p.wtp_spread_frac <= 0:
            return 0.0
        z = markup_frac / self.p.wtp_spread_frac
        return float(1.0 - norm.cdf(z))

    # ---- backward induction -------------------------------------------------

    def _solve(self) -> None:
        """
        Backward induction over (day, inventory_bin, regime). Builds
        `self.value_table[day][bin][regime]` and
        `self.policy_table[day][bin][regime] -> action`.
        """
        n_bins = self.p.n_inventory_bins
        transition_matrix = self.p.regime_params.transition_matrix

        # Terminal value: more inventory left over is worth more (register
        # Section 13.1) -- same principle as dp_toy_example.py's terminal
        # value, generalized to n_bins.
        V_next = {
            regime: [b * self.p.terminal_value_per_bin for b in range(n_bins)] for regime in REGIMES
        }

        value_table = [None] * (self.n_steps + 1)
        policy_table = [None] * self.n_steps
        value_table[self.n_steps] = V_next

        for day in range(self.n_steps - 1, -1, -1):
            V_today = {regime: [0.0] * n_bins for regime in REGIMES}
            policy_today = {regime: [None] * n_bins for regime in REGIMES}

            for regime in REGIMES:
                # Expected continuation value over tomorrow's regime,
                # independent of today's action (the dealer cannot influence
                # the regime) -- computed once per regime per day, reused
                # across every (bin, action) pair below.
                next_regime_probs = transition_matrix[regime]

                for b in range(n_bins):
                    best_value = -np.inf
                    best_action = None
                    for action in ACTIONS:
                        fill_prob = self._fill_prob_cache[action]
                        restock_prob = 1.0 if action == "emergency_purchase" else self.p.daily_restock_prob

                        expected_margin = (
                            fill_prob * self.p.order_size_mean_kg * self.p.reference_price
                            * ACTION_MARKUPS[action]
                        )
                        reward = expected_margin
                        if action == "emergency_purchase":
                            reward += self.p.emergency_purchase_cost
                        if b == 0:
                            reward += self.p.scarcity_penalty

                        # Joint (sell, restock) outcome probabilities, treated
                        # as independent (register Section 13.1, a flagged
                        # simplification).
                        p_sell_only = fill_prob * (1 - restock_prob)
                        p_restock_only = (1 - fill_prob) * restock_prob
                        p_both = fill_prob * restock_prob
                        p_neither = (1 - fill_prob) * (1 - restock_prob)

                        b_down = max(0, b - 1)
                        b_up = min(n_bins - 1, b + 1)

                        continuation = 0.0
                        for next_regime, regime_prob in next_regime_probs.items():
                            V_next_regime = value_table[day + 1][next_regime]
                            expected_over_bin = (
                                p_sell_only * V_next_regime[b_down]
                                + p_restock_only * V_next_regime[b_up]
                                + p_both * V_next_regime[b]  # sale and restock roughly cancel
                                + p_neither * V_next_regime[b]
                            )
                            continuation += regime_prob * expected_over_bin

                        value = reward + continuation
                        if value > best_value:
                            best_value = value
                            best_action = action

                    V_today[regime][b] = best_value
                    policy_today[regime][b] = best_action

            value_table[day] = V_today
            policy_table[day] = policy_today

        self.value_table = value_table
        self.policy_table = policy_table

    # ---- runtime interface ---------------------------------------------------

    def quote_ask(
        self,
        mid_price: float,
        inventory_kg: float = 0.0,
        t: float = 0.0,
        T: float = 1.0,
        regime_name: str | None = None,
        **_ignored_state,
    ) -> float:
        day = min(self.n_steps - 1, int(round((t / T) * self.n_steps))) if T > 0 else 0
        b = self._inventory_to_bin(inventory_kg)
        regime = regime_name if regime_name in REGIMES else "normal"

        action = self.policy_table[day][regime][b]
        self._last_action = action
        markup = ACTION_MARKUPS[action]
        ask = mid_price * (1.0 + markup)

        self.last_diagnostics = {
            "mid_price": mid_price,
            "ask": ask,
            "inventory_kg": inventory_kg,
            "inventory_bin": b,
            "day": day,
            "regime": regime,
            "action": action,
        }
        return ask

    def wants_emergency_purchase(self) -> bool:
        """(Phase 6) Signals whether the LAST quote_ask call selected the
        emergency_purchase action. src/simulation.py checks this once per
        day, for policies that expose it, to decide whether to place a real
        emergency order alongside the quote -- see simulation.py's docstring
        for the exact hook behavior."""
        return getattr(self, "_last_action", None) == "emergency_purchase"

    def restock_markup_frac(self, **_ignored_state) -> float:
        """Same supplier-procurement-premium stand-in as every other policy
        in this project (see policies/fixed_spread.py's docstring)."""
        return ACTION_MARKUPS["normal"]
