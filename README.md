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
| 1 | Simulation core (price process, Poisson demand, accounting, fixed-spread baseline) | ⏳ Not started |
| 2 | Standard Avellaneda–Stoikov reproduction | ⏳ Not started |
| 3 | Physical / committed / in-transit / expected inventory separation | ⏳ Not started |
| 4 | Markov regimes and Hawkes demand | ⏳ Not started |
| 5 | Scarcity-adjusted market-making policy | ⏳ Not started |
| 6 | Dynamic-programming policy | ⏳ Not started |
| 7 | Sector transmission stress test | ⏳ Not started |
| 8 | Statistical rigor (matched Monte Carlo, confidence intervals, holdouts) | ⏳ Not started |
| 9 | Ablation and sensitivity analysis | ⏳ Not started |
| 10 | Validation and historical framing | ⏳ Not started |
| 11 | Germanium extension (stretch goal) | ⏳ Not started |

## Repository structure

```
GaMM-RX/
├── README.md
├── requirements.txt
├── environment.yml
│
├── docs/
│   ├── assumptions_register.md        # every numerical/structural assumption, sourced and labeled
│   ├── README_honesty_paragraph.md    # this project's evidentiary ceiling, written pre-model
│   ├── phase0_research_notes.md       # public research backing the assumptions register
│   ├── model_formulation.md           # (added in later phases)
│   ├── validation_plan.md             # (added in later phases)
│   └── interview_defense_notes.md     # (added in later phases)
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── sources.md
│
├── src/
│   ├── price_process.py
│   ├── regimes.py
│   ├── demand.py
│   ├── supply_chain.py
│   ├── inventory.py
│   ├── accounting.py
│   ├── policies/
│   │   ├── fixed_spread.py
│   │   ├── inventory_heuristic.py
│   │   ├── avellaneda_stoikov.py
│   │   ├── scarcity_adjusted_as.py
│   │   └── dynamic_programming.py
│   ├── simulation.py
│   ├── optimization.py
│   ├── evaluation.py
│   └── visualization.py
│
├── tests/
├── notebooks/
└── results/
    ├── figures/
    ├── tables/
    └── simulation_outputs/
```

Folders without files yet (`src/`, `tests/`, `notebooks/`, `results/`, `data/`) will be
populated starting in Phase 1 and are not created empty in this initial commit.

## Core rule for every component in this repo

Nothing belongs in the final project unless, for that component, this repo can:

1. Explain what it does.
2. Explain why it is included.
3. Defend its assumptions.
4. Describe its limitations.
5. Show what happens when it is removed.

If a component cannot pass that test, it belongs in a **Future Work** section of this
README, not presented as a finished result.

## Documentation index

- [`docs/assumptions_register.md`](docs/assumptions_register.md) — every parameter, its
  value, its meaning, its source type, its justification, and its expected sensitivity.
- [`docs/README_honesty_paragraph.md`](docs/README_honesty_paragraph.md) — the full
  honesty statement and why it was written before any model code.
- [`docs/phase0_research_notes.md`](docs/phase0_research_notes.md) — the public research
  (gallium production concentration, export-control timeline, sector end-uses, and
  modeling-literature rationale) underlying the assumptions register.

## Future work

This section will track components that were explored but did not meet the core rule
above — e.g., candidate features that couldn't be defended, sensitivity-analysis results
that were too fragile to trust, or extensions (like Phase 11's germanium joint-inventory
model) that are explicitly out of scope for the main deliverable.

*(Nothing here yet — Phase 0 only.)*
