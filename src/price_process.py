"""
price_process.py
=================

Phase 1 deliverable: Gallium Price Process.

MODEL
-----
A mean-reverting jump-diffusion (Ornstein-Uhlenbeck base + compound Poisson jumps),
simulated with Euler-Maruyama discretization:

    dS_t = kappa * (theta - S_t) * dt + sigma * S_t * dW_t + J_t * dN_t

where:
    kappa   : speed of mean reversion
    theta   : long-run equilibrium price
    sigma   : continuous (diffusive) volatility, scaled by price level
    dW_t    : Wiener increment
    dN_t    : Poisson jump counter with intensity `jump_intensity`
    J_t     : multiplicative jump size shock to the price level, right-skewed:
              direction is Bernoulli(jump_up_prob), magnitude is drawn from
              Half-Normal(jump_up_scale) if up or Half-Normal(jump_down_scale)
              if down, with jump_up_scale > jump_down_scale by design

WHY MEAN-REVERTING JUMP-DIFFUSION INSTEAD OF PLAIN GBM
--------------------------------------------------------
Gallium is a byproduct commodity with a small number of producers and refiners.
Plain geometric Brownian motion assumes all news arrives continuously and
symmetrically. In reality:
  - There is a fundamental cost-of-production / marginal-supplier level that
    prices tend to revert to during calm periods (mean reversion).
  - Export-control announcements, refinery outages, and sudden demand shocks
    hit the price all at once rather than diffusing in gradually (jumps).
Plain GBM cannot produce the fat left/right tails or the "sudden repricing"
behavior that gallium has historically shown around export-control events.
Mean reversion also keeps the simulated price economically sane over long
horizons (GBM alone can wander to unrealistic price levels).

JUMP ASYMMETRY (register: "Jump size distribution" row, Section 1)
--------------------------------------------------------------------
docs/assumptions_register.md requires jumps to be right-skewed: export
restrictions push prices up sharply, while relief/de-escalation moves are
typically smaller and slower (consistent with the real Jul 2023 -> Dec 2024
-> Nov 2025 escalation pattern in docs/phase0_research_notes.md, where the
ex-China price surge to ~$1,850/kg dwarfed the pace of any downward
correction). This module implements that directly: jump direction is a
biased coin flip (`jump_up_prob`, default > 0.5) and the up-jump and
down-jump magnitudes are drawn from separate half-normal scales
(`jump_up_scale` > `jump_down_scale`), rather than a single symmetric
Normal. An earlier draft of this module used a symmetric Normal jump size
as a placeholder; that was a register violation (no row existed for a
symmetric jump anywhere in the register) and has been corrected here.

REGIME HOOK (STUBBED, NOT FULLY BUILT HERE)
--------------------------------------------
Phase 4 will replace the constant `jump_intensity` / `jump_up_scale` /
`jump_down_scale` with values that depend on a Markov supply regime (Normal /
Delayed / Severe / Recovery) -- per the register, Severe-regime jump intensity
should be "substantially elevated" and Severe-regime jumps should be even
more skewed upward than Normal-regime jumps. To avoid rebuilding the price
process later, this module accepts `regime_jump_intensity_multiplier` and
`regime_jump_size_multiplier` on `step()`, but Phase 1 itself only ever calls
it with the Normal-regime multiplier of 1.0. Treat any regime-dependent
behavior here as UNVALIDATED until Phase 4 lands.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- The up/down jump split is still a simple biased-coin-flip + half-normal
  construction, not a fitted skewed distribution (e.g. a proper skew-normal
  or asymmetric double-exponential). It captures the *direction* of the
  register's requirement (bigger, more frequent up-jumps) but the exact
  shape is still a judgment call, flagged for Phase 9 sensitivity testing.
- kappa, theta, sigma, jump_intensity, jump_up_prob, jump_up_scale,
  jump_down_scale are ALL judgment calls informed by qualitative research,
  not fitted to a price history, because no clean public tick-level gallium
  series exists. Concrete values are logged in
  docs/assumptions_register.md, Section 7 (Phase 1 implementation values).
- Regime-dependent jump intensity/size (register: Section 2, "Jump intensity
  (Severe regime)") is stubbed via `regime_jump_intensity_multiplier` /
  `regime_jump_size_multiplier` but never called with anything other than
  the Normal-regime default of 1.0 in Phase 1 -- exercising it is Phase 4.
- The process can technically produce negative prices if a large downward
  jump coincides with high sigma at a low price level. We floor at a small
  positive epsilon and log a warning count; this is a known crude patch,
  not a resolution.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Every policy (fixed-spread, Avellaneda-Stoikov, scarcity-adjusted, DP) needs
a price path to quote around. Without it there is no simulation at all --
this is the clock the rest of the project runs on.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class PriceProcessParams:
    s0: float = 350.0            # initial price, USD/kg -- register Section 1: "Long-run
                                  # mean price level (normal regime)" cites China-domestic
                                  # low-purity prices ~$420/kg (Oct 2024); 350 chosen as a
                                  # round point within the register's cited ~$300-450 band
    kappa: float = 4.0           # annualized mean-reversion speed (register: "Mean-reversion
                                  # speed" row -- academic-model assumption, no fitted value)
    theta: float = 350.0         # long-run equilibrium price, USD/kg (same register row/
                                  # justification as s0 above)
    sigma: float = 0.35          # annualized diffusive volatility, Normal regime (register:
                                  # "Diffusion volatility (normal regime)" row -- academic-
                                  # model assumption, no public tick data to fit against)
    jump_intensity: float = 3.0  # expected jumps/year, Normal regime (register: "Jump
                                  # intensity (Normal regime)" row -- "rare, on the order of
                                  # a few expected jumps per year")
    jump_up_prob: float = 0.65   # P(jump is upward) -- register: "Jump size distribution"
                                  # row requires right-skew (supply-cut jumps up, sharp;
                                  # relief jumps down, smaller/slower); 0.65 is a judgment
                                  # call implementing that direction, not a fitted value
    jump_up_scale: float = 0.18  # half-normal scale for upward jump magnitude (fraction of
                                  # price) -- judgment call, deliberately larger than
                                  # jump_down_scale per the register's asymmetry requirement
    jump_down_scale: float = 0.07  # half-normal scale for downward jump magnitude --
                                  # judgment call, deliberately smaller than jump_up_scale
    dt: float = 1.0 / 252.0      # daily steps, 252 trading days/year convention
    price_floor: float = 1.0     # hard floor to avoid non-physical non-positive prices


class GalliumPriceProcess:
    """Simulatable mean-reverting jump-diffusion price path."""

    def __init__(self, params: PriceProcessParams, seed: int | None = None):
        self.p = params
        self.rng = np.random.default_rng(seed)
        self.price = float(params.s0)
        self.history = [self.price]
        self.jump_events = 0
        self.jump_up_events = 0
        self.jump_down_events = 0
        self.floor_hits = 0

    def step(self, regime_jump_intensity_multiplier: float = 1.0,
              regime_jump_size_multiplier: float = 1.0) -> float:
        """
        Advance the price process by one dt. Returns the new price.

        regime_jump_intensity_multiplier / regime_jump_size_multiplier:
            Hooks for Phase 4 regime switching. Phase 1 always calls this
            with the defaults (1.0, 1.0), i.e. Normal regime only.
        """
        p = self.p
        s = self.price

        # Diffusive part (Euler-Maruyama on the SDE above)
        dW = self.rng.normal(0.0, np.sqrt(p.dt))
        drift = p.kappa * (p.theta - s) * p.dt
        diffusion = p.sigma * s * dW

        # Jump part: compound Poisson in a dt-sized window
        lam = p.jump_intensity * regime_jump_intensity_multiplier
        n_jumps = self.rng.poisson(lam * p.dt)
        jump_total = 0.0
        if n_jumps > 0:
            self.jump_events += n_jumps
            directions = self.rng.random(n_jumps) < p.jump_up_prob  # True = up
            self.jump_up_events += int(np.sum(directions))
            self.jump_down_events += int(n_jumps - np.sum(directions))

            up_scale = p.jump_up_scale * regime_jump_size_multiplier
            down_scale = p.jump_down_scale * regime_jump_size_multiplier
            magnitudes = np.where(
                directions,
                np.abs(self.rng.normal(0.0, up_scale, size=n_jumps)),
                -np.abs(self.rng.normal(0.0, down_scale, size=n_jumps)),
            )
            jump_total = s * np.sum(magnitudes)

        new_price = s + drift + diffusion + jump_total

        if new_price < p.price_floor:
            new_price = p.price_floor
            self.floor_hits += 1

        self.price = float(new_price)
        self.history.append(self.price)
        return self.price

    def simulate_path(self, n_steps: int) -> np.ndarray:
        """Convenience: simulate n_steps forward from current state, return full history array."""
        for _ in range(n_steps):
            self.step()
        return np.array(self.history)
