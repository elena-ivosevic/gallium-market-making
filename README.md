# Gallium Under Constraint

### Inventory-Aware Dealer Pricing Under Geopolitical Supply Disruption

**Gallium Under Constraint** is a simulation-based research project studying how a physical gallium dealer should price customer orders and manage inventory when supply becomes delayed, unreliable, or politically restricted.

It adapts the inventory-aware logic of the **Avellaneda-Stoikov** market-making framework to a physical commodity setting: shipment lead times, failed deliveries, nonlinear replacement costs, regime-dependent supply conditions, clustered demand, and multiple forms of inventory.

**Central finding:** the result is conditional, not universal. Under the default calibration, the scarcity-adjusted policy does *not* statistically outperform a simple fixed-spread dealer. Across five reserved holdout scenarios, however, it produces a higher mean P&L in four of five — with its strongest performance under persistent, supply-driven disruption, and its weakest when scarcity is demand-driven rather than supply-driven.

[![Holdout scenario policy comparison](https://github.com/elena-ivosevic/gallium-under-constraint/raw/main/results/figures/phase8_holdout_scenario_comparison.png)](/elena-ivosevic/gallium-under-constraint/blob/main/results/figures/phase8_holdout_scenario_comparison.png)

---

## Research Questions

1. Does an Avellaneda-Stoikov-inspired physical-market policy improve dealer performance when gallium supply is disrupted?
2. Can price-based rationing protect military-linked demand on its own, or is an explicit priority-allocation mechanism necessary?

---

## Contribution

Classical market-making models assume a liquid financial asset, observable prices, and two-sided order flow. A physical gallium dealer instead negotiates transactions and replenishes through a supply chain that can be slow, partial, or unreliable. This project makes three contributions:

1. **Physical inventory representation** — physical, committed, available, in-transit, and expected inventory are modeled as five distinct states, not one net position.
2. **Scarcity-adjusted dealer pricing** — the Avellaneda-Stoikov reservation price is extended with bounded premiums for scarcity, replacement cost, shipment risk, existing commitments, and regime severity.
3. **Price rationing vs. explicit allocation** — a separate military-priority overlay tests whether price sensitivity alone protects military-linked demand, or whether explicit allocation is needed.

This is a structured decision model for studying dealer behavior under specified assumptions — not a validated forecasting system or deployable trading strategy.

---

## Project at a Glance

- 271 passing tests across 28 modules
- 5 dealer-pricing policies + 1 priority-allocation overlay
- 4 supply regimes · 4 customer sectors
- Matched-seed Monte Carlo evaluation with paired significance testing
- 5 reserved holdout scenarios · 9 policy ablations · 11-parameter sensitivity analysis
- Full assumptions register with source classification for every parameter

---

## Key Results

**Default calibration (40 matched seeds):** fixed spread has the highest mean P&L; the scarcity-adjusted policy underperforms it but not significantly (p = 0.141). Standard Avellaneda-Stoikov, unmodified, materially underperforms — its spread is too narrow for physical replenishment risk.

**Holdout scenarios:** scarcity-adjusted pricing wins in 4 of 5 — most dramatically under a persistent Severe regime (mean loss reduced by ~$4.15M vs. fixed spread). It loses only when scarcity is demand-driven rather than supply-driven, since the policy has no direct demand-pressure premium.

**Biggest driver:** shipment reliability, not price volatility. It produces the largest swing (~$271K) in the sensitivity analysis, and removing the shipment-risk premium alone cuts mean P&L by ~$45K — more than any other single component.

**Two informative null results:** the explicit military-priority overlay adds almost nothing (military-linked orders already fill at ~47.5% vs. 18.3% civilian, purely from price sensitivity), and the dynamic-programming extension doesn't beat the simpler scarcity-adjusted rule — its exact solution to a simplified state space loses to a heuristic with better information.

[![Sensitivity tornado chart](https://github.com/elena-ivosevic/gallium-under-constraint/raw/main/results/figures/phase9_tornado_chart.png)](/elena-ivosevic/gallium-under-constraint/blob/main/results/figures/phase9_tornado_chart.png)

Full tables, confidence intervals, and figures are in the [accompanying paper](docs/) and `results/figures/`.

---

## Scope

Physical gallium trades over an opaque, negotiated market with no public order book or dealer-level transaction data. The model is therefore evaluated through internal-consistency tests, matched-seed comparisons, holdouts, ablations, and sensitivity analysis — **not** backtested against real dealer performance. Any comparative claim should be read as *"Policy A outperforms Policy B under the assumptions specified here,"* not as a claim about real-world gallium markets.

---

## Repository Structure

```
gallium-under-constraint/
├── docs/                   # assumptions register, dev log, research notes
├── src/
│   ├── price_process.py, demand.py, inventory.py, accounting.py
│   ├── supply_chain.py, regimes.py, simulation.py
│   ├── evaluation.py, holdout_scenarios.py, ablation.py, sensitivity.py, validation.py
│   └── policies/           # fixed_spread, inventory_heuristic, avellaneda_stoikov,
│                            # scarcity_adjusted_as, priority_overlay, dynamic_programming
├── tests/                  # 271 passing tests
└── results/figures/
```

---

## Installation

```bash
git clone https://github.com/elena-ivosevic/gallium-under-constraint.git
cd gallium-under-constraint
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v
```

---

## Limitations

- Scenario-based, not statistically calibrated to proprietary dealer data
- No customer sell-side order flow; regime transitions and several behavioral parameters are judgment calls
- The dynamic-programming policy solves a simplified internal model, not the full simulation
- One-at-a-time sensitivity analysis doesn't capture parameter interactions
- Single dealer, single commodity, no explicit competitor behavior

Full detail: [`docs/assumptions_register.md`](docs/assumptions_register.md) · [`docs/development_log.md`](docs/development_log.md)

---

## Author

**Elena Ivosevic** — independent quantitative research on market microstructure, physical inventory risk, and critical-mineral pricing.

## License

[MIT License](LICENSE)
