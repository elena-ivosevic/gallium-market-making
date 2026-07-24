# GaMM-RX — Gallium Market-Making with Regime & eXposure Modeling

A simulation-based research project exploring how a physical-commodity dealer might
quote, hedge, and manage inventory for gallium — a thinly traded, geopolitically exposed
critical mineral — under supply-chain disruption and panic-driven demand.

The project builds up from a naive fixed-spread baseline, through a faithful
reproduction of the Avellaneda–Stoikov market-making model, to a scarcity-aware policy
that accounts for physical inventory, shipment risk, and regime-dependent supply
conditions, and (as a stretch goal) a dynamic-programming policy that reasons about the
future value of preserved inventory.

---

## What this project is, and what it is not

> Gallium is an opaque, thinly traded, largely negotiated physical market without a
> public order book or comprehensive transaction tape. Global primary production is
> concentrated almost entirely in one country, annual volumes are small (on the order of
> a few hundred metric tons worldwide), and most transactions are bilateral and
> undisclosed. No dataset of realized gallium-dealer bid/ask quotes, fill rates, or
> profits is publicly available, and this project does not have access to any
> proprietary one.
>
> As a result, the regime probabilities, shipment-reliability assumptions,
> customer-demand parameters, and sector inventory figures used in this project are
> **hand-specified scenarios informed by public industry research** — U.S. Geological
> Survey production data, export-control reporting, and industry price commentary — and
> are **not estimates statistically fitted to proprietary dealer data**, because no such
> data exists to fit them to. Every parameter of this kind is labeled explicitly in
> [`docs/assumptions_register.md`](docs/assumptions_register.md) as Real data,
> Analogous-market estimate, Academic-model assumption, or Judgment call, and that label
> is the honest description of its evidentiary weight.
>
> Consequently, this model is evaluated through **internal consistency checks,
> sensitivity analysis, simulated holdout scenarios, and qualitative comparisons with
> known supply disruptions** — not through a historical backtest of realized
> gallium-dealer profits. Any claim in this project of the form "Policy A outperforms
> Policy B" should be read as **"Policy A outperforms Policy B under this project's
> stated scenario assumptions,"** with an explicit confidence interval, not as a claim
> about what a real gallium dealer would have earned.
>
> Similarly, any comparison to real-world events (such as China's 2023–2025 gallium
> export controls) is offered as a **qualitative plausibility check**, not a calibration
> exercise, and not a claim that the model predicts or explains actual historical
> prices, shortages, or industrial outcomes. Sector-level results describe the behavior
> of **simulated customers** under assumed parameters — they are not estimates of real
> industrial production or real economic loss.
>
> This project is a decision-modeling and market-microstructure exercise built on
> defensible, clearly labeled assumptions — not a validated forecasting or trading
> system for the physical gallium market.

The full version of this statement, along with the reasoning for writing it before any
model code existed, is in
[`docs/README_honesty_paragraph.md`](docs/README_honesty_paragraph.md).

---

## Project status

| Phase | Description | Status |
|---|---|---|
| 0 | Research, assumptions register, honesty paragraph | ✅ Complete |
| 1 | Simulation core (price process, Poisson demand, accounting, fixed-spread baseline) | ✅ Complete |
| 2 | Standard Avellaneda–Stoikov reproduction | ✅ Complete |
| 3 | Physical / committed / in-transit / expected inventory separation | ⏳ Not started |
| 4 | Markov regimes and Hawkes demand | ⏳ Not started |
| 5 | Scarcity-adjusted market-making policy | ⏳ Not started |
| 6 | Dynamic-programming policy | ⏳ Not started |
| 7 | Sector transmission stress test | ⏳ Not started |
| 8 | Statistical rigor (matched Monte Carlo, confidence intervals, holdouts) | ⏳ Not started |
| 9 | Ablation and sensitivity analysis | ⏳ Not started |
| 10 | Validation and historical framing | ⏳ Not started |
| 11 | Germanium extension (stretch goal) | ⏳ Not started |

## Documentation index

- [`docs/assumptions_register.md`](docs/assumptions_register.md) — every parameter, its
  value, its meaning, its source type, its justification, and its expected sensitivity.
  Section 7 logs Phase 1's concrete numeric values; Section 8 logs Phase 2's
  (Avellaneda-Stoikov and the inventory heuristic), including a calibration-dependent
  finding worth reading before trusting any Phase 2 P&L comparison.
- [`docs/README_honesty_paragraph.md`](docs/README_honesty_paragraph.md) — the full
  honesty statement and why it was written before any model code.
- [`docs/phase0_research_notes.md`](docs/phase0_research_notes.md) — the public research
  underlying the assumptions register.

## Core rule for every component in this repo

Nothing belongs in the final project unless, for that component, this repo can:

1. Explain what it does.
2. Explain why it is included.
3. Defend its assumptions.
4. Describe its limitations.
5. Show what happens when it is removed.

If a component cannot pass that test, it belongs in the **Future Work** section below,
not presented as a finished result.

---

## Phase 1 — Simulation Core

Phase 1 builds the environment every later policy will be tested in, plus the simplest
possible policy to serve as a floor. Every numeric parameter used below has a row in
`docs/assumptions_register.md`, Section 7 — none were invented at the code level without
being logged there (three were, during a first pass, and are flagged and corrected in
Section 7's "Known deviations" note, along with a jump-distribution bug of the same kind).

### Components built

| Module | What it does | Why it's included | Key limitation |
|---|---|---|---|
| `src/price_process.py` | Mean-reverting jump-diffusion price path (OU + right-skewed compound Poisson jumps) | Plain GBM can't produce the sudden repricing / fat-tail behavior gallium shows around supply shocks (register §1); mean reversion keeps long paths economically sane | Jump asymmetry is a biased-coin + half-normal construction, not a fitted skewed distribution; regime-dependent jump parameters are stubbed but unexercised until Phase 4 |
| `src/demand.py` | Poisson customer arrivals, lognormal order sizes, price-dependent execution | Simplest defensible null model for order arrivals (register §4); price-dependent fills are what makes spread choice matter at all | No sector structure, no demand clustering (Poisson only — Hawkes is Phase 4) |
| `src/accounting.py` | Cash, inventory, weighted-average cost basis, realized P&L, mark-to-market P&L, terminal wealth, **and a minimal instant-restock rule** | A dealer needs a scoreboard; the restock rule exists only so inventory doesn't hit zero and stop the simulation | Restock is instant with no lead time or failure probability — scaffolding, explicitly to be replaced by the real supply chain in Phase 3 (register §3) |
| `src/policies/fixed_spread.py` | Constant ask markup to customers (register §6 "Fixed ask spread") plus a constant restock markup (register §6 "Fixed bid spread," reinterpreted — see below) | Establishes the floor every smarter policy must beat | The "bid spread" is currently a supplier procurement premium, not a genuine customer-facing bid, because Phase 1's demand model has no customer sell-side flow — a real limitation, not a naming quirk |
| `src/simulation.py` | Orchestrates price → demand → quote → fill → restock → snapshot, once per day | Lets every future, smarter policy be tested against identical price/demand paths (needed for Phase 8's matched Monte Carlo) | Daily time step only; single dealer, single commodity, no competitors |

### Tests

26 tests across 4 files, all passing:

```
tests/test_price_process.py   — price-process behavior: positivity, floor,
                                 jump-intensity effect, right-skew (register §1),
                                 mean reversion
tests/test_demand.py          — order generation and order execution
tests/test_accounting.py      — inventory updates, cash updates, restock
                                 (shipment-arrival stand-in), P&L calculations
tests/test_policies.py        — baseline policy behavior, end-to-end
                                 simulation, determinism, and the Phase 1
                                 mastery checkpoint (below)
```

Run them with:

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Mastery checkpoint (predict, confirm, and correct when the data disagrees)

**Original prediction:** raising jump intensity in the price process should increase the
cross-seed variance of terminal dealer P&L, since bigger/more frequent price dislocations
widen the gap between "sold right before a jump" and "sold right after a jump" outcomes.

**What was actually found:** raw price-path variance across seeds *does* rise with jump
intensity, exactly as compound-Poisson theory predicts. But cross-seed **dealer P&L**
variance for the fixed-spread policy goes the *other way* — it falls as jump intensity
rises, holding per-jump size fixed. Verified mechanism: with strong mean reversion, a low
jump intensity means most years contain zero or one jump, and whether that one jump lands
before or after the dealer happens to trade is close to a coin flip that swings terminal
wealth hard — a bimodal, idiosyncratic outcome. A high jump intensity exposes the dealer
to many small jumps instead, and the net trading effect across many jumps converges more
across seeds than the "one big jump, good or bad timing" story does, even though the
underlying price series is objectively noisier.

This is recorded as a **corrected finding**, not quietly patched — see
`tests/test_policies.py::test_mastery_checkpoint_jump_intensity_raises_price_variance_but_not_pnl_variance`
and `docs/assumptions_register.md` Section 7, deviation #4.

### Demo run

A single 252-trading-day run of the fixed-spread baseline (`ask_spread_frac = 0.04`,
`bid_markup_frac = 0.03`, seed = 42):

- Final price: $399.70/kg (started at $350.00/kg)
- 255 customer orders arrived; 51 filled (~20% fill rate)
- 7 automatic restock events, 0 failed sales (never ran dry)
- Realized P&L: $87,916 · Mark-to-market P&L: $84,735 · Terminal wealth: $134,735

The ~20% fill rate is not incidental — it falls out directly from the model: with a 4%
ask markup and customer willingness-to-pay dispersed as ±5% around mid price, the
fraction of customers whose WTP exceeds the ask is `P(Z ≥ 0.04/0.05) ≈ 21%`, matching the
simulated ~20% almost exactly. That the simulation reproduces a number derivable by hand
is the kind of internal-consistency check this project leans on in place of a backtest.

See `results/figures/phase1_demo_run.png` for price, inventory, and mark-to-market P&L
over the run.

### Explicit Phase 1 limitations (Core Rule test)

- **Price process:** jump asymmetry is a biased-coin/half-normal construction, not a
  fitted skew distribution; regime-dependent jump parameters (register §2) are stubbed
  but never exercised outside the Normal-regime multiplier of 1.0 until Phase 4.
- **Demand:** homogeneous Poisson only, no sectors (register §4), no clustering, hard
  fill/no-fill threshold rather than a smooth fill-probability curve.
- **Accounting/restock:** instant, zero-failure restocking — a placeholder, not a supply
  chain. Phase 3 replaces this entirely with lead times (register §3), partial/failed
  deliveries, and separate physical / committed / in-transit / expected inventory.
- **Policy:** the fixed-spread baseline is deliberately dumb by design — its limitation
  *is* its purpose. Its "bid spread" is a procurement premium stand-in, not a genuine
  customer-facing bid (see table above).

If any of these components were removed: the price process removal leaves nothing to
quote around (no simulation at all); the demand module removal leaves the dealer with no
one to sell to (no revenue, no P&L differences between policies); the accounting module
removal leaves no way to score a policy; the restock stub's removal causes every policy
to sell out of inventory and halt early, since Phase 3's real supply chain isn't built
yet.

---

## Phase 2 — Standard Avellaneda–Stoikov Model

Phase 2 reproduces the standard, closed-form Avellaneda-Stoikov (2008) inventory-aware
market-making model, and compares it against both Phase 1 comparison points the roadmap
calls for: the fixed-spread baseline and a new inventory-threshold heuristic.

### Components built

| Module | What it does | Why it's included | Key limitation |
|---|---|---|---|
| `src/policies/avellaneda_stoikov.py` | Reservation price `r = s - q·γ·σ²·(T-t)`, optimal spread `δ = γσ²(T-t) + (2/γ)ln(1+γ/k)`, quotes `ask = r + δ/2`, `bid = r - δ/2` | The standard, citable inventory-aware quoting model (register `phase0_research_notes.md` §5) that every later scarcity/DP extension builds on | `sigma` is converted from price_process.py's fractional vol via `sigma_abs = sigma_frac * mid_price` — a documented adaptation, not an exact match to the underlying mean-reverting jump-diffusion; `k` is tuned for plausible spread magnitude, not fitted to `src/demand.py`'s actual hard-threshold fill model |
| `src/policies/inventory_heuristic.py` | Step-function ask adjustment: extra markup when inventory ≤ a low threshold, discount when ≥ a high threshold, base markup otherwise | The roadmap-required middle comparison point — shows whether AS's benefit (if any) comes from being inventory-aware at all, or from its specific continuous, theoretically-derived adjustment shape | Discontinuous by construction (a 1 kg inventory move across a threshold jumps the quote); thresholds are judgment calls, logged in the register |
| `src/simulation.py` (extended) | Now passes `t`, `T` (years), and `sigma` (fractional) to every policy's `quote_ask`, and records any policy's `last_diagnostics` dict generically | Lets AS use time-to-horizon and volatility without hardcoding policy-specific logic into the simulation loop; the generic diagnostics hook means no `isinstance` branching is needed to plot AS-specific internals later | Fixed-spread and inventory-heuristic policies simply ignore the new `t`/`T`/`sigma` kwargs via the shared interface |

### Tests

21 new tests across 3 files (47 total, all passing):

```
tests/test_avellaneda_stoikov.py    — reservation-price sign/magnitude behavior,
                                       risk-aversion scaling, time-horizon decay,
                                       spread properties, invalid-parameter guards
tests/test_inventory_heuristic.py   — threshold behavior, boundary inclusivity
tests/test_phase2_comparison.py     — matched-path structural comparisons across
                                       all three policies (NOT outcome-superiority
                                       claims — see file docstring for why)
```

Run them with `python -m pytest tests/ -v`.

### Mastery checkpoint (write from memory, then check against this)

**The formula:**

```
r(s, t) = s - q · γ · σ² · (T - t)
δ = γσ²(T - t) + (2/γ)·ln(1 + γ/k)
ask = r + δ/2        bid = r - δ/2
```

**Why inventory enters the formula:** a dealer holding inventory carries price risk on
it. The reservation price is not "the market price" — it's the price at which the dealer,
*given their current position*, is indifferent to holding one more unit. Inventory risk
has to enter the price the dealer is willing to trade at, or the quote says nothing about
the dealer's actual exposure.

**Why excess inventory lowers the quote:** more inventory (`q` large and positive) means
more downside risk if price falls, so the dealer's true indifference point sits below mid
— they'd rather sell some off, even at a discount. The minus sign in `s - q·γ·σ²·(T-t)`
is what encodes "sell it down."

**Why risk aversion strengthens the adjustment:** `γ` multiplies the entire inventory-risk
term. A more risk-averse dealer demands a bigger price concession for the same inventory
and the same volatility — this falls directly out of the formula, not from a separate
assumption.

**Why the effect shrinks near the end of the trading horizon:** both the reservation shift
and the first spread term scale with `(T - t)`. As `t → T`, that factor → 0, so holding
inventory near the end carries less *future* price risk simply because there's less
future left. The spread doesn't fully collapse, though — the `(2/γ)ln(1+γ/k)` term is
independent of time remaining and persists even at `t = T` (order-flow/adverse-selection
compensation, confirmed in `test_spread_does_not_fully_collapse_at_horizon_end`).

### Demo output

`results/figures/phase2_as_diagnostics.png` — mid price, reservation price, bid, and ask
over one simulated year, plus inventory, quoted spread, and cash. Reservation price
tracks mid price closely (inventory-driven deviations are on the order of a few dollars
at ~200 kg inventory, as tuned — see the register), and the quoted spread stays in a
roughly 2.5–3% band, widening slightly with volatility and inventory swings.

`results/figures/phase2_pnl_distribution_preview.png` — terminal mark-to-market P&L
across 60 matched seeds for all three policies. This is a **single-seed-per-run preview**
of the kind of comparison Phase 8 does properly (with confidence intervals and paired
tests) — not a substitute for it.

### A finding worth reading before trusting any Phase 2 number

At this phase's calibration (`γ = 3.5e-6`, `k = 0.2`), Avellaneda-Stoikov quotes a much
tighter average markup (~0.53%) than the fixed-spread baseline (4.00%) — thinner, in fact,
than the 3% restock markup, meaning the dealer is often selling close to or below its own
replenishment cost. Fill rate roughly doubles (≈42% vs. ≈20%), but average mark-to-market
P&L across 60 matched seeds comes out lower (~$48,000 vs. ~$80,500 for fixed-spread).

**This is not a claim that Avellaneda-Stoikov underperforms in general.** `γ` and `k` are
both registered as judgment calls with Sensitivity: High, explicitly slated for Phase 9's
sweep — this result is a consequence of *this* calibration, not of the model's structure.
It's recorded honestly (register §8) so that a future Phase 9 sweep showing different `k`
values produce different outcomes reads as "the sweep did its job," not as a contradiction
of an unstated claim made here.

### Explicit Phase 2 limitations (Core Rule test)

- AS's `sigma` is adapted from a fractional/multiplicative process into an absolute-vol
  approximation; the underlying SDE also has mean reversion and jumps that the classical
  AS derivation doesn't model at all.
- AS's assumed order-arrival intensity, `λ(δ) = A·exp(-k·δ)`, is not the execution model
  `src/demand.py` actually uses (a hard willingness-to-pay threshold) — `k` is tuned for
  plausible spread magnitude, not fitted to match that mismatch away.
- Inventory `q` enters as raw kilograms, not centered on a target/safety-stock level —
  faithful to the original paper, but it means zero inventory (not safety-stock-level
  inventory) is this module's reservation-price-neutral point. Phase 5 recenters this.
- The inventory heuristic's thresholds and adjustment sizes are judgment calls with no
  prior register row — logged in Section 8 now, per this project's own rule.
- Neither AS nor the heuristic yet has a genuine customer-facing bid (see Phase 1
  limitations, unchanged) — `restock_markup_frac` remains a supplier-procurement-premium
  stand-in for both.

If Phase 2 were removed: there would be no principled, inventory-aware quoting policy for
Phase 5's scarcity-adjusted model to extend, and no evidence (however preliminary) of
*how* an inventory-aware policy's behavior actually differs from a naive one — only the
claim that it should, in theory.

---

## Repository structure (current)

```
GaMM-RX/
├── README.md
├── requirements.txt
├── docs/
│   ├── assumptions_register.md
│   ├── README_honesty_paragraph.md
│   └── phase0_research_notes.md
├── src/
│   ├── price_process.py
│   ├── demand.py
│   ├── accounting.py
│   ├── simulation.py
│   └── policies/
│       ├── fixed_spread.py
│       ├── inventory_heuristic.py
│       └── avellaneda_stoikov.py
├── tests/
│   ├── test_price_process.py
│   ├── test_demand.py
│   ├── test_accounting.py
│   ├── test_policies.py
│   ├── test_avellaneda_stoikov.py
│   ├── test_inventory_heuristic.py
│   └── test_phase2_comparison.py
└── results/
    └── figures/
        ├── phase1_demo_run.png
        ├── phase2_as_diagnostics.png
        └── phase2_pnl_distribution_preview.png
```

Modules planned by the full roadmap (`regimes.py`, `supply_chain.py`,
`scarcity_adjusted_as.py`, `dynamic_programming.py`, `optimization.py`, `evaluation.py`,
`visualization.py`, and the full `notebooks/` tree) do not exist yet and are not implied
to exist by this README — they are listed in the project roadmap as future work, not
represented here as finished.

## Future Work

- Everything in Phases 3–11 of the roadmap: real supply-chain inventory, regime
  switching, Hawkes demand, the scarcity-adjusted policy, dynamic programming, sector
  stress testing, matched Monte Carlo with confidence intervals, ablation/sensitivity
  analysis, and qualitative historical validation.
- Phase 9's planned sweep of `γ` and `k` — needed before the Phase 2 "AS underperforms at
  this calibration" finding can be read as anything more than a single-point observation.
- A genuine customer-facing bid (currently `bid_markup_frac`/`restock_markup_frac` are
  supplier procurement-premium stand-ins — see Phase 1/2 limitations above) once customer
  sell-side flow exists.
- A smoother (non-threshold) fill-probability function for customer orders, which would
  also let `k` be fitted to the actual execution model instead of tuned by feel.
- A properly fitted skewed jump-size distribution (currently a biased-coin/half-normal
  approximation of the register's right-skew requirement).
