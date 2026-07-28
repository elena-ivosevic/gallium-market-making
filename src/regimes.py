"""
regimes.py
==========

Phase 4 deliverable: Markov Supply Regimes.

WHAT THIS MODULE DOES
----------------------
Tracks a discrete Markov chain over four supply-chain states -- Normal,
Delayed, Severe, Recovery -- and exposes, for the CURRENT regime, the
multipliers/values every other module needs to behave differently by
regime:
  - price jump intensity/size multipliers (consumed by price_process.py's
    existing `step(regime_jump_intensity_multiplier, regime_jump_size_multiplier)`
    hooks, which were stubbed in Phase 1 specifically for this)
  - civilian and military shipment reliability (consumed by supply_chain.py's
    existing `SupplyChainParams.reliability` / `reliability_military` fields,
    which simulation.py now updates once per day based on the current regime)
  - a demand-intensity multiplier and Hawkes excitation strength (consumed by
    demand.py's sector/Hawkes order flow)

WHY A MARKOV CHAIN, NOT A DETERMINISTIC SCHEDULE
------------------------------------------------------
Real supply disruptions do not follow a fixed calendar -- nobody knows in
advance exactly when an export-control escalation will happen or how long it
will last. A Markov chain with persistence (high self-transition
probabilities) captures "regimes last a while and transition
stochastically" without pretending to forecast the exact timing, which no
model reasonably could. This is also directly testable: Phase 10's
validation checklist can confirm regimes actually persist for multiple
periods rather than flickering, and that Severe is reachable only through
Delayed (matching the real 2023 licensing -> 2024 ban escalation), not
before either has been exercised.

WHY THE TRANSITION MATRIX IS ASYMMETRIC (escalation-biased, not a random walk)
------------------------------------------------------------------------------------
docs/assumptions_register.md, Section 11.3, hand-specifies a matrix where:
  - Normal can only move to Delayed (never straight to Severe)
  - Severe can only be reached from Delayed
  - Recovery can relapse into Severe (small probability), reflecting the
    real 2025 suspension being explicitly conditional and revocable
  - Normal is by far the most persistent state (~333-day expected duration)
This asymmetry is a direct, documented translation of the real 2023 -> 2024
-> 2025 escalation-then-partial-recovery pattern
(docs/phase0_research_notes.md, Section 2) into a stochastic process, not an
arbitrary choice.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Only one real historical escalation cycle exists to inform this matrix
  qualitatively; there is no fitted multi-cycle transition data, and there
  cannot be, for a market with this little history of discrete regime
  episodes. Register Section 11.3 states this explicitly.
- The chain is memoryless (transition probabilities depend only on the
  CURRENT regime, not how long the dealer has already been in it) -- a true
  semi-Markov model with duration-dependent hazard rates would be more
  realistic but adds complexity with no data to justify the extra
  parameters.
- Regime transitions are checked once per simulated day; intra-day regime
  changes are not modeled (consistent with the project's daily time step
  throughout).

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Every policy would keep quoting as if supply conditions never change --
there would be no way to observe how a scarcity-aware policy (Phase 5)
behaves differently in Severe vs. Normal conditions, which is the entire
point of building one.
"""

from dataclasses import dataclass, field
import numpy as np

REGIMES = ("normal", "delayed", "severe", "recovery")


@dataclass
class RegimeParams:
    # Register Section 11.3
    transition_matrix: dict = field(default_factory=lambda: {
        "normal":   {"normal": 0.997, "delayed": 0.003, "severe": 0.000, "recovery": 0.000},
        "delayed":  {"normal": 0.010, "delayed": 0.980, "severe": 0.010, "recovery": 0.000},
        "severe":   {"normal": 0.000, "delayed": 0.000, "severe": 0.985, "recovery": 0.015},
        "recovery": {"normal": 0.005, "delayed": 0.000, "severe": 0.003, "recovery": 0.992},
    })
    # Register Section 11.1
    jump_intensity_multiplier: dict = field(default_factory=lambda: {
        "normal": 1.0, "delayed": 2.0, "severe": 6.0, "recovery": 2.5,
    })
    jump_size_multiplier: dict = field(default_factory=lambda: {
        "normal": 1.0, "delayed": 1.3, "severe": 2.0, "recovery": 1.2,
    })
    # Register Section 11.2
    civilian_reliability: dict = field(default_factory=lambda: {
        "normal": 0.95, "delayed": 0.70, "severe": 0.40, "recovery": 0.75,
    })
    military_reliability: dict = field(default_factory=lambda: {
        "normal": 0.75, "delayed": 0.45, "severe": 0.15, "recovery": 0.40,
    })
    # Register Section 11.7 -- linearly interpolated between normal/severe
    # excitation via the same regime "severity rank" used for the other
    # multipliers (normal=0, delayed=1, severe=2, recovery=1, on a 0-2 scale
    # matching how far each regime sits from calm conditions)
    hawkes_excitation: dict = field(default_factory=lambda: {
        "normal": 0.05, "delayed": 0.30, "severe": 0.60, "recovery": 0.20,
    })
    # Register Section 11.1-adjacent: demand-intensity multiplier (panic
    # buying raises order arrival rates, not just jump risk) -- judgment
    # call, same qualitative escalation shape as the other regime multipliers
    demand_intensity_multiplier: dict = field(default_factory=lambda: {
        "normal": 1.0, "delayed": 1.2, "severe": 2.5, "recovery": 1.5,
    })
    initial_regime: str = "normal"


class RegimeSwitcher:
    """Stochastic Markov chain over the four supply regimes, stepped once per day."""

    def __init__(self, params: RegimeParams, seed: int | None = None):
        self.p = params
        self.rng = np.random.default_rng(seed)
        for regime in REGIMES:
            if regime not in params.transition_matrix:
                raise ValueError(f"transition_matrix missing row for regime '{regime}'")
        if params.initial_regime not in REGIMES:
            raise ValueError(f"initial_regime must be one of {REGIMES}")
        self.current_regime = params.initial_regime
        self.history: list[str] = [self.current_regime]
        self.regime_days: dict = {r: 0 for r in REGIMES}
        self.regime_days[self.current_regime] += 1

    def step(self) -> str:
        """Advance one day: draw the next regime from the current regime's
        transition row. Returns the new (possibly unchanged) regime."""
        row = self.p.transition_matrix[self.current_regime]
        regimes = list(row.keys())
        probs = list(row.values())
        self.current_regime = self.rng.choice(regimes, p=probs)
        self.history.append(self.current_regime)
        self.regime_days[self.current_regime] += 1
        return self.current_regime

    # ---- per-regime lookups used by other modules -------------------------

    def jump_intensity_multiplier(self) -> float:
        return self.p.jump_intensity_multiplier[self.current_regime]

    def jump_size_multiplier(self) -> float:
        return self.p.jump_size_multiplier[self.current_regime]

    def civilian_reliability(self) -> float:
        return self.p.civilian_reliability[self.current_regime]

    def military_reliability(self) -> float:
        return self.p.military_reliability[self.current_regime]

    def hawkes_excitation(self) -> float:
        return self.p.hawkes_excitation[self.current_regime]

    def demand_intensity_multiplier(self) -> float:
        return self.p.demand_intensity_multiplier[self.current_regime]
