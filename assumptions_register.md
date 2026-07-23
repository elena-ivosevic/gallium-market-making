# Assumptions Register — GaMM-RX (Gallium Market-Making with Regime & eXposure modeling)

Every numerical or structural assumption used anywhere in this project must have a row
here before it is used in code. If a parameter changes during development, update its row
— do not leave stale numbers in this file.

**Source-type labels (every row must use exactly one):**

- **Real data** — taken directly from a cited public source (USGS, CSIS, Fastmarkets,
  peer-reviewed literature) without material adjustment.
- **Analogous-market estimate** — inferred by analogy from a different but related market
  (e.g., other thinly-traded critical minerals, other export-control episodes) because no
  gallium-specific number exists.
- **Academic-model assumption** — a parameter whose role comes from the structure of a
  published model (Avellaneda–Stoikov, Hawkes, jump-diffusion, Markov-switching) rather
  than from measurement, e.g. a risk-aversion coefficient or a decay rate.
- **Judgment call** — hand-specified by the project author because no data source, close
  analogy, or model-structural constraint determines it; chosen to produce a plausible,
  internally consistent scenario.

Sensitivity is a qualitative forecast (to be confirmed in Phase 9): **High** = expected to
materially change headline conclusions if wrong; **Medium** = expected to change magnitude
but not direction of conclusions; **Low** = expected to have marginal effect.

---

## 1. Market structure and price process

| Parameter | Value | Meaning | Source type | Justification | Sensitivity |
|---|---|---|---|---|---|
| China share of primary gallium production | 98% | Fraction of world primary gallium output produced in China | Real data | USGS Mineral Commodity Summaries and CSIS both report 98–99%; 98% used as a conservative round point estimate | Low (structural fact, not a tunable model input) |
| Global annual primary gallium production | ~700 metric tons | Approximate size of the physical market | Real data | Industry tracking (713 t in 2023) cited to justify "thin market" framing | Low |
| Long-run mean price level (normal regime) | Calibrated to a reference spot price, e.g. ~$300–450/kg | Center of mean reversion in the price process | Real data / Judgment call (hybrid) | Anchored to reported China-domestic low-purity prices (~$420/kg, Oct 2024) since outside-China prices are currently distorted by the export ban; exact figure is a judgment call within a real-data-informed range | Medium |
| Ex-China price premium during Severe regime | Up to ~4x normal-regime level | Captures the bifurcated market (China-domestic vs. rest-of-world) | Real data | Reported spot prices outside China reached ~$1,850/kg (Apr 2026) vs. steady China-domestic prices, a >200% rise from a lower base | High |
| Diffusion volatility (normal regime) | — (calibrated, not disclosed here at implementation-detail level) | Day-to-day continuous price noise absent jumps | Academic-model assumption | No public tick-level gallium data exists to estimate this directly; chosen to produce plausible calm-period price paths | Medium |
| Mean-reversion speed | — | Rate at which price pulls back toward the regime-dependent long-run level | Academic-model assumption | Standard feature of commodity price models; magnitude is a judgment call absent a fitted time series | Medium |
| Jump intensity (Normal regime) | Low (e.g., rare, on the order of a few expected jumps per year) | Probability per unit time of a discrete price jump | Judgment call | No fitted arrival-rate estimate exists; set low to represent quiet baseline conditions consistent with long calm stretches in the historical record | High |
| Jump intensity (Severe regime) | Substantially elevated vs. Normal | Probability per unit time of a discrete price jump during acute disruption | Judgment call, informed by real data | Historical episodes (Jul 2023, Dec 2024, Jan 2025 announcements) show clustered, discrete repricing events within a period of months, motivating a materially higher intensity in Severe | High |
| Jump size distribution | Right-skewed (larger upside jumps than downside) | Magnitude of price jumps when they occur | Analogous-market estimate | Reflects the asymmetric nature of export-restriction shocks (supply cuts push prices up sharply; relief moves are typically smaller/slower) seen across critical-mineral episodes generally | Medium |

## 2. Supply regimes (Markov switching)

| Parameter | Value | Meaning | Source type | Justification | Sensitivity |
|---|---|---|---|---|---|
| Number of regimes | 4 (Normal, Delayed, Severe, Recovery) | Discrete states of the supply environment | Academic-model assumption | Chosen to mirror the real escalation pattern: warning-shot licensing (Delayed-like) → explicit ban (Severe) → partial, conditional suspension (Recovery) → baseline (Normal) | Medium |
| Normal-regime shipment reliability | 95% | Probability a shipment arrives successfully | Judgment call, informed by research | Represents stable supply conditions prior to 2023 controls | Medium |
| Delayed-regime shipment reliability | 70% | Probability a shipment arrives successfully, with longer lead times | Judgment call | Represents the initial licensing-requirement period (2023), which slowed but did not stop most flows | High |
| Severe-regime shipment reliability | 40% | Probability a shipment arrives successfully | Scenario assumption / Judgment call | Represents the Dec 2024 explicit export ban period, during which reporting indicates shipments to the U.S. largely did not resume in meaningful volume | High |
| Recovery-regime shipment reliability | 75% | Probability a shipment arrives successfully during partial normalization | Judgment call | Represents a conditional, revocable suspension (as of Nov 2025) rather than a full return to Normal; deliberately kept below Normal to reflect the source material's framing of this as "a pause, not a resolution" | High |
| Regime transition matrix | — (to be specified in `regimes.py`, not restated here) | Probability of moving between regimes each period | Judgment call | No fitted multi-state transition data exists for a market with only a handful of qualitatively distinct historical episodes; matrix entries are hand-specified to produce persistence (regimes last multiple periods) and a bias toward escalation before de-escalation, consistent with the observed 2023→2024→2025 pattern | High |
| Expected duration of Severe regime | On the order of months, not days or years | Average time spent in Severe before transitioning | Judgment call, informed by research | Real escalation-to-partial-resolution cycle took roughly 2 years (Jul 2023 to Nov 2025); a single simulated "Severe" episode is scaled to a fraction of that, since the full historical arc actually spans multiple regime transitions, not one continuous Severe period | High |

## 3. Inventory and supply chain

| Parameter | Value | Meaning | Source type | Justification | Sensitivity |
|---|---|---|---|---|---|
| Shipment lead time (Normal) | Short, fixed baseline (e.g., days to low weeks) | Time between order and arrival under normal conditions | Judgment call | No public dealer logistics data exists; chosen to be short relative to the simulation horizon so "Normal" genuinely feels low-friction | Medium |
| Lead-time inflation factor (Delayed/Severe) | Multiplicative increase over Normal lead time | Captures longer, more variable lead times during disruption | Judgment call | Directionally motivated by reporting of rebuilding stock outside China becoming "difficult" under committed-end-use licensing requirements | High |
| Safety stock level | Fixed number of kilograms, set relative to average sector demand | Minimum inventory buffer the dealer tries not to breach | Judgment call | Standard supply-chain practice; exact level is not derived from a real dealer's policy (none public) | High |
| Replacement-cost curvature parameter | Convex (cost rises faster than linearly as available inventory falls) | Governs how sharply emergency replacement cost increases near scarcity | Academic-model assumption | Standard way to represent scarcity premia in inventory-cost literature; convexity direction is well-motivated (replacement of the last units is disproportionately expensive), exact curvature magnitude is a judgment call | High |
| Committed-inventory treatment | Subtracted from physical inventory before computing "available" inventory | Distinguishes inventory already owed to customers from freely quotable inventory | Academic-model assumption | Definitional choice needed to avoid double-counting promised units as freely available; not a measured quantity | Medium |
| Expected-inventory discounting | Probability-weighted, not treated as equivalent to physical stock | E.g., 200 kg shipment at 50% arrival probability contributes 100 kg to "expected" but not "available" inventory | Academic-model assumption | Core project design choice (see Phase 3); directly testable via the required numerical example contrasting expected vs. physical inventory | High |

## 4. Demand (Poisson + Hawkes) and customer sectors

| Parameter | Value | Meaning | Source type | Justification | Sensitivity |
|---|---|---|---|---|---|
| Sector set | Semiconductors, Defense & Aerospace, Telecommunications, Solar/Clean Energy | Customer segmentation | Real data (sector existence) / Judgment call (parameterization) | Sectors themselves are real, well-documented gallium end-uses; the specific arrival rates, order sizes, and willingness-to-pay assigned to each are judgment calls, since no public per-sector transaction data exists | Medium |
| Base order-arrival rate per sector | — (sector-relative, e.g. Semiconductors > Telecom > Solar > Defense in frequency) | Poisson base rate of customer orders | Judgment call | Ordering reflects qualitative sector descriptions (semiconductor demand is high-volume/high-frequency; defense is low-frequency but high urgency and high willingness-to-pay) rather than measured order books | Medium |
| Sector willingness-to-pay ranking | Defense & Aerospace highest, Solar lowest | Relative price sensitivity by sector | Analogous-market estimate | Consistent with public commentary that defense/aerospace applications are low-substitutability and mission-critical, while solar applications compete with cheaper alternative materials at the margin | Medium |
| Hawkes baseline intensity | — | Background (non-excited) demand arrival rate | Academic-model assumption | Structural parameter of the Hawkes process; magnitude chosen for plausible baseline order flow, not measured | Medium |
| Hawkes excitation strength (branching ratio) | Moderate-to-high during Severe regime, low during Normal | Degree to which one order raises the probability of subsequent orders | Model assumption | No fitted branching-ratio estimate for gallium exists; regime-dependence is motivated by the intuition that panic clustering should be much stronger when scarcity fears are already elevated | High |
| Hawkes decay rate | — | Speed at which the excitation (panic) effect fades after an order | Model assumption | Controls persistence of demand clustering; chosen so a single urgent order's influence fades over a period of days to weeks rather than instantly or permanently, since no data exists to fit this directly | High |

## 5. Dealer policy parameters (Avellaneda–Stoikov and extensions)

| Parameter | Value | Meaning | Source type | Justification | Sensitivity |
|---|---|---|---|---|---|
| Risk-aversion coefficient (γ) | — (to be swept in Phase 9) | Strength of inventory-risk penalty in reservation price | Academic-model assumption | Standard Avellaneda–Stoikov parameter; no gallium-dealer-specific estimate exists, so it is treated as a design/tuning parameter and explicitly sensitivity-tested rather than fixed by data | High |
| Order-arrival sensitivity parameter (k) | — | Governs how quickly a customer's fill probability falls as the quoted price moves away from a reference price | Academic-model assumption | Standard Avellaneda–Stoikov parameter; judgment call in the absence of fitted execution data | High |
| Trading horizon length | Fixed simulation length (e.g., one representative planning period) | Time window over which the dealer's terminal-wealth objective is defined | Judgment call | Chosen to be long enough to observe multiple regime transitions, short enough to keep "terminal P&L" a meaningful, interpretable objective | Medium |
| Scarcity-premium functional form | Increasing and convex in (safety stock − available inventory) | Governs how much the reservation price rises as available inventory approaches safety stock | Academic-model assumption | Directionally required by the project's core hypothesis (Phase 5); functional form and magnitude are judgment calls, ablation-tested in Phase 9 | High |

## 6. Fixed baseline (non-adaptive) policy

| Parameter | Value | Meaning | Source type | Justification | Sensitivity |
|---|---|---|---|---|---|
| Fixed bid spread | Constant, e.g. a flat percentage or absolute markdown off mid-price | Baseline dealer's constant buy-side markdown | Judgment call | Deliberately naive; exists purely as a floor benchmark every later policy must beat, not as a realistic dealer strategy | Low (by design — it is meant to be simple, not accurate) |
| Fixed ask spread | Constant, symmetric or asymmetric markup off mid-price | Baseline dealer's constant sell-side markup | Judgment call | Same rationale as fixed bid spread | Low |

---

## 7. Phase 1 implementation values (concrete numbers instantiated in code)

Sections 1–6 above intentionally leave many parameter VALUES as "—" (correctly:
Phase 0 fixes the parameter's *role, source type, and justification*, not
necessarily an exact number, since several rows are meant to be swept in Phase 9).
This section logs the concrete numeric values Phase 1 code actually uses, each
tied back to its Section 1–6 row, so no number exists in code without a row here.

| Code parameter | Value | Register row it instantiates | Source type | Notes |
|---|---|---|---|---|
| `PriceProcessParams.s0` | 350.0 (USD/kg) | §1 Long-run mean price level (normal regime) | Real data / Judgment call | Round point inside the cited ~$300–450 band |
| `PriceProcessParams.theta` | 350.0 (USD/kg) | §1 Long-run mean price level (normal regime) | Real data / Judgment call | Same anchor as s0 |
| `PriceProcessParams.kappa` | 4.0 (annualized) | §1 Mean-reversion speed | Academic-model assumption | No fitted value exists; chosen for a ~2-month reversion half-life |
| `PriceProcessParams.sigma` | 0.35 (annualized, fraction of price) | §1 Diffusion volatility (normal regime) | Academic-model assumption | No public tick data to fit against |
| `PriceProcessParams.jump_intensity` | 3.0 (expected jumps/year, Normal) | §1 Jump intensity (Normal regime) | Judgment call | "Rare, a few per year" per register wording |
| `PriceProcessParams.jump_up_prob` | 0.65 | §1 Jump size distribution (right-skew) | Judgment call | Implements the register's required upward skew in jump *frequency* |
| `PriceProcessParams.jump_up_scale` | 0.18 | §1 Jump size distribution (right-skew) | Judgment call | Implements the register's required upward skew in jump *magnitude* |
| `PriceProcessParams.jump_down_scale` | 0.07 | §1 Jump size distribution (right-skew) | Judgment call | Deliberately smaller than jump_up_scale |
| `DemandParams.arrival_rate_per_year` | 250.0 | §4 Base order-arrival rate per sector (pre-sector, aggregate placeholder) | Judgment call | Sector-level split is Phase 4; this is a single aggregate rate |
| `DemandParams.order_size_mean_kg` | 25.0 | (no existing row — new) | Judgment call | Not previously registered; flagged below as a gap |
| `DemandParams.wtp_spread_frac` | 0.05 | (no existing row — new) | Judgment call | Not previously registered; flagged below as a gap |
| `AccountingParams.restock_threshold_kg` | 50.0 | §3 Safety stock level | Judgment call | |
| `AccountingParams.restock_amount_kg` | 150.0 | (no existing row — new) | Judgment call | Not previously registered; flagged below as a gap |
| `FixedSpreadParams.ask_spread_frac` | 0.04 | §6 Fixed ask spread | Judgment call | Deliberately naive by design |
| `FixedSpreadParams.bid_markup_frac` | 0.03 | §6 Fixed bid spread (reinterpreted) | Judgment call | See deviation note below — this is NOT a customer-facing bid in Phase 1 |
| `AccountingParams.initial_cash` | $50,000 | (no existing row — new) | Judgment call | Scenario-setup starting capital, not a market parameter; sized to be comparable to several restock events' worth of inventory value |
| `AccountingParams.initial_inventory_kg` | 200.0 kg | (no existing row — new) | Judgment call | Scenario-setup starting inventory; sized above `restock_threshold_kg` so the demo run doesn't restock on day one |

### Known deviations from this register, found during Phase 1 implementation

These are logged here rather than silently patched, per this file's own rule
that stale/incorrect rows must be struck through or annotated, not deleted:

1. **§6 "Fixed bid spread" reinterpreted.** The register describes this as a
   dealer's constant buy-side markdown quoted to customers. Phase 1's demand
   model (`src/demand.py`) only generates customer BUY requests — there is no
   customer sell-side flow yet — so there is nothing for a customer-facing bid
   to quote against. `FixedSpreadParams.bid_markup_frac` currently stands in
   for the markup the dealer pays when restocking from the external supply
   market, not a customer-facing bid. If/when customer sell-side flow is added
   (e.g. recyclers), this should split into two distinct, separately-registered
   parameters. See `src/policies/fixed_spread.py` docstring for the same note.
2. **Four implementation parameters (`order_size_mean_kg`, `restock_amount_kg`,
   `initial_cash`, `initial_inventory_kg`) were added to code without a prior
   row here** — a direct violation of this file's rule #1 ("no parameter is
   added to code before it has a row here"). All four are now logged in the
   table above as of this Phase 1 pass. Treat their absence before this point
   as a process error that has been caught and corrected, not as evidence the
   values themselves are wrong.
3. **An earlier Phase 1 draft used symmetric `Normal(jump_mean, jump_std)` jump
   sizes**, contradicting §1's "Jump size distribution" row (right-skewed,
   required). This has been corrected: `price_process.py` now draws jump
   direction from a biased coin (`jump_up_prob`) with separate up/down
   half-normal scales (`jump_up_scale` > `jump_down_scale`). The symmetric
   version should never have been implemented without a corresponding register
   row justifying the deviation, and none existed.
4. **Mastery-checkpoint prediction corrected, not forced.** Phase 1's roadmap
   mastery checkpoint asks: "Predict what should happen to terminal P&L
   variance when jump intensity rises." The naive prediction (variance rises)
   holds for the raw PRICE process (confirmed: compound-Poisson variance
   scales with intensity, verified in `tests/test_policies.py`), but the
   opposite holds for cross-seed dealer P&L variance under the fixed-spread
   policy specifically, because rare low-intensity jumps create idiosyncratic,
   trade-timing-dependent outcomes (did the one jump happen before or after
   the dealer traded?) that dominate cross-seed spread more than the smoother,
   more law-of-large-numbers-like effect of frequent small jumps. This is
   recorded as a corrected finding, not deleted or hidden — see
   `tests/test_policies.py::test_mastery_checkpoint_jump_intensity_raises_price_variance_but_not_pnl_variance`.

---

## Notes on how to use this table

1. No parameter is added to code before it has a row here.
2. "Real data" rows should carry a specific source in `phase0_research_notes.md`; if a
   number in code and a number in this table diverge, the table is wrong and must be
   fixed.
3. Rows with Sensitivity = High are prime candidates for the Phase 9 tornado chart —
   do not let the sensitivity analysis "discover" that a parameter matters if it was
   already flagged High here; the point of Phase 9 is to confirm or overturn this prior
   labeling, not to duplicate it.
4. This table will grow. Do not delete superseded rows — strike through or annotate
   them, so the project's evolution stays auditable.
