# Gallium Under Constraint

## Inventory-Aware Dealer Pricing Under Geopolitical Supply Disruption

**Gallium Under Constraint** is a simulation-based research project examining how a physical gallium dealer should price customer orders and manage inventory when supply becomes delayed, unreliable, or politically restricted.

The project adapts the inventory-aware logic of the Avellaneda-Stoikov market-making framework to a physical commodity setting with shipment lead times, failed deliveries, nonlinear replacement costs, regime-dependent supply conditions, clustered demand, and multiple forms of inventory.

The central conclusion is conditional rather than universal. Under the default calibration, the scarcity-adjusted policy does not statistically outperform a simple fixed-spread dealer. Across five reserved holdout scenarios, however, it produces a higher mean P&L in four, with its strongest relative performance occurring when disruption is persistent and supply-driven. It performs poorly when scarcity is caused primarily by demand volume without corresponding deterioration in the supply-risk signals it observes.

![Holdout scenario policy comparison](results/figures/phase8_holdout_scenario_comparison.png)

---

## Research Questions

1. **Does an Avellaneda-Stoikov-inspired physical-market policy improve dealer performance when gallium supply is disrupted?**

2. **Can price-based rationing protect military-linked demand on its own, or is an explicit priority-allocation mechanism necessary?**

---

## Research Contribution

Traditional market-making models are designed for liquid financial markets with observable prices, continuous trading, and two-sided order flow. Physical gallium markets operate differently. Transactions are negotiated, supply is slow to replenish, shipments may arrive partially or fail entirely, and inventory cannot be treated as immediately replaceable.

This project makes three principal contributions:

1. **Physical inventory representation**

   The simulation separates physical, committed, available, in-transit, and expected inventory rather than representing inventory as a single immediately usable quantity.

2. **Scarcity-adjusted dealer pricing**

   The standard Avellaneda-Stoikov reservation price is extended with bounded premiums for scarcity, replacement cost, shipment risk, existing commitments, and regime severity.

3. **Price rationing versus explicit allocation**

   A separate military-priority overlay tests whether price sensitivity alone protects military-linked demand or whether an explicit allocation rule improves access during genuine inventory contention.

The result is a structured decision model for studying dealer behavior under specified assumptions. It is not presented as a validated forecasting system, historical backtest, or deployable trading strategy.

---

## Project at a Glance

* **271 passing tests**
* **Five dealer-pricing policies**
* **One separate priority-allocation overlay**
* **Four supply regimes**
* **Four customer sectors**
* **Matched-seed Monte Carlo evaluation**
* **Five reserved holdout scenarios**
* **Nine policy ablations**
* **Eleven-parameter sensitivity analysis**
* **Mathematical, edge-case, and qualitative validation**
* **A complete assumptions register with source classifications**

All core modeling, evaluation, sensitivity, and validation phases are complete.

---

## Scope and Interpretation

Gallium is an opaque and thinly traded physical commodity without a public order book, comprehensive transaction tape, or publicly available dealer-level history of quotes, executions, and profits.

The project therefore cannot be calibrated or backtested against realized gallium-dealer performance. It is evaluated through:

* Internal-consistency tests
* Matched-seed Monte Carlo comparisons
* Confidence intervals and paired statistical tests
* Reserved holdout scenarios
* Component ablations
* Parameter sensitivity analysis
* Mathematical and edge-case validation
* Qualitative comparison with documented supply disruptions

Any statement that one policy outperforms another should be interpreted as:

> **Policy A outperforms Policy B under the simulation assumptions specified in this repository.**

It should not be interpreted as a claim about what a real gallium dealer would have earned.

The project is also more accurately described as **inventory-aware physical-commodity dealer pricing** than conventional two-sided electronic market making. Customer demand is modeled primarily on the buy side, while replenishment occurs through suppliers rather than customer sell orders. Avellaneda-Stoikov is used as a theoretical foundation and adapted to the economics of a physical supply chain.

---

## Model Architecture

### Market Environment

| Component              | Implementation                                                                                        |
| ---------------------- | ----------------------------------------------------------------------------------------------------- |
| Reference price        | Mean-reverting jump-diffusion process with asymmetric positive shocks                                 |
| Supply conditions      | Four-state Markov regime process                                                                      |
| Demand arrivals        | Sector-specific Poisson and Hawkes order flow                                                         |
| Customer behavior      | Order-size and willingness-to-pay distributions with price-sensitive execution                        |
| Military-linked demand | Per-order classification with lower modeled price sensitivity                                         |
| Physical supply        | Lead times, full deliveries, partial deliveries, failed deliveries, and emergency procurement         |
| Replacement cost       | Nonlinear replenishment cost that increases under supply stress                                       |
| Inventory              | Physical, committed, available, in-transit, and expected inventory                                    |
| Dealer accounting      | Cash, realized P&L, mark-to-market P&L, terminal wealth, backlog penalties, and failed-delivery costs |

The separation between inventory states is economically important. For example, 200 kilograms in transit with a 50 percent delivery probability is not equivalent to 100 kilograms already held in the warehouse. Only physical inventory can satisfy an immediate customer obligation with certainty.

### Supply Regimes

The market environment transitions among four supply states:

| Regime   | Interpretation                                                    |
| -------- | ----------------------------------------------------------------- |
| Normal   | Stable supply and relatively reliable replenishment               |
| Delayed  | Longer lead times and moderate deterioration in reliability       |
| Severe   | Major disruption, low reliability, and elevated replacement costs |
| Recovery | Improving conditions with continued risk of relapse               |

### Customer Sectors

The demand model includes:

* Semiconductors
* Defense and Aerospace
* Telecommunications
* Solar and Clean Energy

Each sector has distinct arrival intensity, order-size behavior, and military-linked demand share.

---

## Policies Compared

| Policy                               | Purpose                                                                                    |
| ------------------------------------ | ------------------------------------------------------------------------------------------ |
| Fixed spread                         | Naive benchmark using a constant customer markup                                           |
| Inventory heuristic                  | Simple threshold-based adjustment based on inventory                                       |
| Standard Avellaneda-Stoikov          | Classical inventory-aware reservation price and spread                                     |
| Scarcity-adjusted Avellaneda-Stoikov | Main policy incorporating physical supply risk                                             |
| Finite-state dynamic programming     | Policy that explicitly values preserved future inventory                                   |
| Priority overlay                     | Separate allocation rule that prioritizes military-linked orders during genuine contention |

---

## Scarcity-Adjusted Pricing Policy

The main policy begins with the standard Avellaneda-Stoikov reservation price and adds five bounded physical-market premiums:

```math
r_t^{\mathrm{physical}}
=
r_t^{\mathrm{AS}}
+ P_{\mathrm{scarcity}}
+ P_{\mathrm{replacement}}
+ P_{\mathrm{shipment}}
+ P_{\mathrm{commitment}}
+ P_{\mathrm{regime}}
```

The individual premiums represent distinct sources of physical-market risk:

* **Scarcity premium:** increases as freely available inventory approaches the safety-stock threshold.
* **Replacement-cost premium:** reflects the increasing cost of replenishing inventory during disruption.
* **Shipment-risk premium:** increases when incoming supply becomes less reliable.
* **Commitment premium:** accounts for inventory that is already owed to customers.
* **Regime premium:** reflects the broader severity of the supply environment.

The premiums are additive, non-negative, and capped to prevent unstable or economically implausible quotes.

The military-priority overlay is deliberately separate from the pricing policy. It changes order-processing priority only when military-linked and civilian orders compete for insufficient physical inventory during the same period. This separation permits a direct comparison between price-based rationing and explicit allocation.

---

## Evaluation Framework

Policies are evaluated using matched random seeds so that they face the same simulated price, demand, and regime conditions as closely as possible.

The evaluation framework reports:

* Mean outcomes with 95 percent confidence intervals
* Paired policy differences
* Paired t-tests
* Tail-loss measures
* Overall fill rates
* Sector-level fill rates
* Military-linked and civilian fill rates
* Shortage frequency and duration
* Holdout-scenario performance
* Component ablations
* One-at-a-time parameter sensitivity
* Mathematical and edge-case validation

Price, demand, and regime random streams are matched across policies. Supply streams are reproducibly seeded, but policies may place replenishment orders at different times and in different quantities. Shipment events are therefore not perfectly paired one-for-one across every policy.

No headline policy comparison is treated as meaningful without uncertainty information.

---

## Main Results

### 1. Default Full-Regime Comparison

Across 40 matched seeds:

| Policy                               | Mean mark-to-market P&L | 95% confidence interval | Paired p-value vs. fixed spread |
| ------------------------------------ | ----------------------: | ----------------------: | ------------------------------: |
| Fixed spread                         |                -$37,803 |    [-$139,594, $63,988] |                             N/A |
| Standard Avellaneda-Stoikov          |               -$572,992 |  [-$850,745, -$295,240] |                         <0.0001 |
| Scarcity-adjusted Avellaneda-Stoikov |               -$109,545 |   [-$144,428, -$74,663] |                           0.141 |
| Dynamic programming                  |               -$125,561 |    [-$297,990, $46,868] |                           0.031 |

![Policy comparison with confidence intervals](results/figures/phase8_policy_comparison_with_ci.png)

The fixed-spread policy has the highest mean P&L under the default full-regime calibration. The scarcity-adjusted policy has a lower point estimate, but its paired difference from fixed spread is not statistically distinguishable from zero at 40 seeds.

Standard Avellaneda-Stoikov materially underperforms at the selected calibration because its quoted spread is too narrow relative to the cost of replenishing physical inventory.

### 2. Performance Depends on the Source of Stress

| Holdout scenario                                    | Fixed-spread mean P&L | Scarcity-adjusted mean P&L | Higher mean P&L   |
| --------------------------------------------------- | --------------------: | -------------------------: | ----------------- |
| Persistent Severe regime                            |           -$4,599,300 |              **-$448,737** | Scarcity-adjusted |
| Low volatility with extreme shipment failure        |              -$41,666 |               **-$17,643** | Scarcity-adjusted |
| High demand with moderate prices                    |         **-$306,610** |                  -$624,447 | Fixed spread      |
| Sudden recovery followed by relapse                 |             -$873,136 |              **-$311,982** | Scarcity-adjusted |
| Military supply near zero with civilian supply open |             -$325,556 |               **-$93,123** | Scarcity-adjusted |

The scarcity-adjusted policy produces a higher mean P&L when disruption is driven by risks that it explicitly observes, including regime severity, shipment failure, and replacement cost.

It performs poorly when scarcity is driven mainly by demand volume while its supply-risk signals remain moderate.

The central finding is therefore not that a more complex policy is universally superior. Its value depends on whether the source of market stress matches the risks represented in the pricing rule.

### 3. Shipment Reliability Is the Dominant Assumption

The eleven-parameter sensitivity analysis identifies shipment reliability as the largest driver of mean P&L, with a total measured swing of approximately **$271,000**.

![Sensitivity tornado chart](results/figures/phase9_tornado_chart.png)

The component-ablation results support the same conclusion:

* Removing the **shipment-risk premium** reduces mean P&L by approximately **$45,329**.
* Removing the **scarcity premium** changes mean P&L by approximately **$4,460**.
* Removing the **commitment premium** produces no measurable effect at the default calibration.
* Removing all physical-market premiums and reverting to standard Avellaneda-Stoikov reduces mean P&L by approximately **$427,484**.

The combined physical-risk framework has a substantially larger effect than any single premium in isolation.

### 4. Pricing Protects Military-Linked Demand Under the Default Calibration

Before the explicit priority overlay is applied, military-linked orders fill at approximately **47.5 percent**, compared with **18.3 percent** for civilian orders.

This difference is driven by the model’s assumed price-sensitivity gap. Military-linked customers are less price-sensitive and therefore continue executing at quotes that screen out more civilian demand.

The explicit priority overlay produces almost no aggregate improvement at the default calibration. Its P&L and fill-rate curves remain nearly flat as strictness increases from `p = 0` to `p = 1`.

![Priority overlay frontier](results/figures/phase9_overlay_frontier.png)

This is a meaningful null result. Conservative replenishment behavior keeps physical inventory sufficiently high that genuine same-day contention is uncommon. An allocation rule cannot materially change outcomes when there is little contention to resolve.

### 5. Adaptive Pricing Can Prevent the Shortage It Is Expected to Reveal

Under a permanently Severe regime, the scarcity-adjusted policy raises its markup enough to reduce customer execution. Physical inventory consequently remains higher and stockouts occur less frequently than under Normal conditions.

This initially appeared inconsistent with the expectation that Severe conditions should produce greater scarcity. The mechanism is endogenous price rationing. The policy responds to supply stress by suppressing demand before physical inventory is exhausted.

The result is retained rather than recalibrated away because it reflects the actual behavior of the policy.

---

## Dynamic Programming Extension

The project includes a finite-state dynamic-programming policy that explicitly compares immediate profit with the future value of preserving inventory.

The policy is solved through backward induction over a discretized state space containing inventory bins, supply regimes, and time. It differs from the other policies because it uses a precomputed action table instead of a closed-form pricing rule.

At the current calibration, the dynamic-programming policy does not outperform the simpler scarcity-adjusted policy. Its internal transition model intentionally simplifies the full simulation and does not completely represent the jump-diffusion price process, Hawkes demand, sector structure, or physical supply chain.

This result illustrates an important modeling principle: greater mathematical complexity does not guarantee better performance when the optimization model differs materially from the environment in which its policy is evaluated.

---

## Research and Engineering Discipline

A central objective of the project is to make assumptions, failures, and null results auditable.

The repository includes:

* A complete assumptions register maintained throughout development
* Source classifications for every material parameter
* Pre-registered ablation hypotheses
* Matched-seed policy comparisons
* Regression tests for discovered implementation errors
* Explicit corrections when point estimates failed statistical testing
* Documentation of components that produced no measurable effect
* Tests showing how the model changes when individual components are removed
* Separate treatment of implementation validity, simulated performance, and real-world interpretation

Documented corrections include:

* An initially unbounded replacement-cost function
* Reorder triggers that fired repeatedly during an existing shortfall
* Incomplete accounting for failed-delivery costs
* Mutation of shared scenario parameters across runs
* A shipment-reliability sensitivity override that initially had no effect in regime mode

These corrections are retained as part of the research record rather than removed from the narrative.

---

## Validation

The validation framework addresses three questions.

### Do the mathematical relationships behave as intended?

Examples include:

* More inventory lowers the Avellaneda-Stoikov reservation price.
* Higher volatility widens the quoted spread.
* Lower shipment reliability raises the shipment-risk premium.
* Lower available inventory raises the scarcity premium.
* Greater commitments increase the physical-market reservation price.

### Do important edge cases collapse correctly?

Examples include:

* Perfect shipment reliability produces a zero shipment-risk premium.
* Unlimited inventory produces a zero scarcity premium.
* Zero Hawkes excitation produces Poisson-like demand variance.
* Zero military-linked demand share produces no military-linked orders.
* A Normal-only transition matrix never leaves the Normal regime.

### Does the model respond plausibly under Severe conditions?

Most directional relationships behave as expected. The primary exceptions are economically informative. Scarcity premiums and stockouts do not necessarily increase under Severe conditions because the policy raises prices and reduces execution before inventory is exhausted.

Historical events are used only as qualitative plausibility checks. The project is not calibrated to realized gallium prices, dealer transactions, or historical dealer profits.

![Validation summary](results/figures/phase10_validation_summary.png)

---

## Repository Structure

```text
gallium-under-constraint/
├── README.md
├── LICENSE
├── requirements.txt
├── docs/
│   ├── assumptions_register.md
│   ├── development_log.md
│   ├── README_honesty_paragraph.md
│   └── phase0_research_notes.md
├── src/
│   ├── price_process.py
│   ├── demand.py
│   ├── inventory.py
│   ├── accounting.py
│   ├── supply_chain.py
│   ├── regimes.py
│   ├── simulation.py
│   ├── sector_stress_test.py
│   ├── evaluation.py
│   ├── holdout_scenarios.py
│   ├── ablation.py
│   ├── sensitivity.py
│   ├── validation.py
│   └── policies/
│       ├── fixed_spread.py
│       ├── inventory_heuristic.py
│       ├── avellaneda_stoikov.py
│       ├── scarcity_adjusted_as.py
│       ├── priority_overlay.py
│       ├── dp_toy_example.py
│       └── dynamic_programming.py
├── tests/
└── results/
    └── figures/
```

The detailed chronological development record is preserved in [`docs/development_log.md`](docs/development_log.md). The main README focuses on the final research question, methodology, findings, and limitations.

---

## Installation and Testing

```bash
git clone https://github.com/elena-ivosevic/gallium-under-constraint.git
cd gallium-under-constraint

python -m venv .venv
source .venv/bin/activate

# Windows:
# .venv\Scripts\activate

pip install -r requirements.txt
python -m pytest tests/ -v
```

The current test suite contains **271 passing tests**.

---

## Reproducibility

The simulation logic, assumptions, tests, and generated figures are versioned in the repository.

The test suite can be reproduced with a single command. The complete experiment suite is not yet consolidated into one entry point that regenerates every table and figure from raw seed-level results.

A complete reproducibility pipeline should eventually save:

* Raw seed-level results
* Experiment configuration files
* Tables used in the accompanying paper
* Generated figures
* A run manifest containing the code commit, package versions, and random seeds

This limitation is disclosed rather than implying that the current repository already provides full one-command replication.

---

## Limitations

* The model is scenario-based rather than statistically calibrated to proprietary dealer data.
* There is no genuine customer sell-side order flow or active customer-facing bid.
* The regime transition matrix and several behavioral parameters are judgment calls informed by limited public evidence.
* Military-linked demand is represented through modeled price sensitivity and contract-like backlog behavior rather than observed procurement records.
* The dynamic-programming policy solves a simplified internal model that differs from the complete simulation environment.
* One-at-a-time sensitivity analysis does not identify interactions among parameters.
* Confidence intervals use a t-distribution approximation rather than bootstrap methods.
* Sector outputs describe simulated customers and should not be interpreted as estimates of real industrial production loss.
* Policy-dependent shipment decisions prevent shipment outcomes from being perfectly paired event-for-event across policies.
* The model studies one dealer and one commodity without explicit competitor behavior.

These limitations define the scope of the conclusions. They are not resolved simply by increasing model complexity.

---

## Documentation

* [`docs/assumptions_register.md`](docs/assumptions_register.md) records every material parameter, source classification, justification, and expected sensitivity.
* [`docs/development_log.md`](docs/development_log.md) preserves the phase-by-phase research and implementation history.
* [`docs/README_honesty_paragraph.md`](docs/README_honesty_paragraph.md) provides the complete scope and claims statement.
* [`docs/phase0_research_notes.md`](docs/phase0_research_notes.md) summarizes the public research used to construct the simulation scenarios.

---

## Next Steps

The highest-value next steps concern reproducibility and research communication rather than additional model complexity:

1. Consolidate the experiment suite into a single reproducible pipeline.
2. Save raw seed-level outputs and complete configuration manifests.
3. Add continuous integration for the test suite.
4. Convert the research notes into a citation-complete bibliography.
5. Write the accompanying paper around the project’s central conditional finding.
6. Build a public results dashboard without changing the underlying research claims.

---

## Author

**Elena Ivosevic**

Independent quantitative research project examining market microstructure, physical inventory risk, supply-chain disruption, and critical-mineral pricing.

---

## License

This project is released under the [MIT License](LICENSE).
