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

## 8. Phase 2 implementation values (Avellaneda-Stoikov + inventory heuristic)

| Code parameter | Value | Register row it instantiates | Source type | Notes |
|---|---|---|---|---|
| `AvellanedaStoikovParams.risk_aversion` (gamma) | 3.5e-6 | §5 Risk-aversion coefficient (γ) | Academic-model assumption | Tuned so a ~200 kg inventory position produces a reservation-price shift of a few percent of price (verified numerically, see notes below), not an unrealistic multiple of it. To be swept in Phase 9 as the register already flags (Sensitivity: High) |
| `AvellanedaStoikovParams.k` | 0.2 | §5 Order-arrival sensitivity parameter (k) | Academic-model assumption | Tuned so the order-flow spread term is a plausible magnitude; NOT fitted to `src/demand.py`'s actual hard-threshold execution model (a real, flagged mismatch — see below) |
| `AvellanedaStoikovParams.restock_markup_frac` | 0.03 | §6 Fixed bid spread (reinterpreted, same as Phase 1) | Judgment call | Same supplier-procurement-premium stand-in as `FixedSpreadParams.bid_markup_frac` |
| Simulation horizon `T` | `n_steps * dt` (1.0 year for a 252-day run) | §5 Trading horizon length | Judgment call | Simply the simulation's own length; not derived from a real dealer planning cycle |
| `InventoryHeuristicParams.low_threshold_kg` | 80.0 | (no existing row — new) | Judgment call | Chosen above `AccountingParams.restock_threshold_kg` (50.0) so the heuristic reacts to scarcity before the auto-restock stub fires |
| `InventoryHeuristicParams.high_threshold_kg` | 250.0 | (no existing row — new) | Judgment call | Chosen above `AccountingParams.initial_inventory_kg` (200.0) so "excess" is a genuinely elevated state, not the default starting point |
| `InventoryHeuristicParams.low_inventory_extra_frac` | 0.03 | (no existing row — new) | Judgment call | |
| `InventoryHeuristicParams.high_inventory_discount_frac` | 0.02 | (no existing row — new) | Judgment call | |
| `InventoryHeuristicParams.base_ask_spread_frac` | 0.04 | §6 Fixed ask spread (reused) | Judgment call | Deliberately matches the fixed-spread baseline's markup so any P&L difference is attributable to inventory-awareness logic, not a different base markup |

### Sigma unit conversion (an adaptation, logged here for auditability)

`price_process.py`'s `sigma` is fractional/multiplicative (`sigma * S_t * dW`).
The classical Avellaneda-Stoikov derivation assumes constant ABSOLUTE
volatility. `avellaneda_stoikov.py` converts via `sigma_abs = sigma_frac *
mid_price`, evaluated fresh at each quote. This is a local approximation of
an SDE that also has mean reversion and jumps that the plain AS derivation
does not model at all — see the "Sigma unit conversion" section of
`src/policies/avellaneda_stoikov.py`'s docstring for the full discussion.

### A finding from this calibration, logged honestly rather than smoothed over

Running all three Phase 1/2 policies on 60 matched seeds (same price/demand
paths per seed — a single-seed-per-run preview of Phase 8's proper matched
Monte Carlo, NOT a substitute for it) found:

| Policy | Mean ask markup over mid | Mean fill rate | Mean mark-to-market P&L (60 seeds) |
|---|---|---|---|
| Fixed-spread | 4.00% | ~20% | ~$80,500 |
| Inventory heuristic | ~4.00% (varies by regime) | ~20–25% | ~$78,900 |
| Avellaneda-Stoikov | **~0.53%** | ~42% | **~$48,000** |

At `gamma=3.5e-6, k=0.2`, AS's average realized ask markup (0.53%) is
noticeably thinner than even `restock_markup_frac` (3%) — meaning that, on
average, the dealer is quoting close to (and on many orders, below) its own
replenishment cost, despite roughly doubling its fill rate versus the
fixed-spread baseline. This is a genuine, calibration-dependent consequence
of the chosen `k` (which governs how tight the order-flow term of the
spread is), not a claim that Avellaneda-Stoikov "underperforms" the simpler
policies in general. `k` and `gamma` are both flagged in this register as
Sensitivity: High and explicitly slated for Phase 9's sweep — this result
is exactly the kind of thing that sweep should confirm or overturn, not a
conclusion to draw from a single, non-statistical, 60-seed preview. It is
recorded here so that a future Phase 9 result showing a different `k`
producing a different outcome is read as "the sweep did its job," not as a
contradiction of an unstated earlier claim.

---

## 9. Phase 3 implementation values (supply-chain mechanics + inventory tranches)

| Code parameter | Value | Register row it instantiates | Source type | Notes |
|---|---|---|---|---|
| `SupplyChainParams.lead_time_days` | 14 | §3 Shipment lead time (Normal) | Judgment call | "Days to low weeks," per the register's own wording |
| `SupplyChainParams.reliability` | 0.95 | §2 Normal-regime shipment reliability | Judgment call, informed by research | Reused directly — Phase 4's regime switch does not exist yet, so this project has only ever exercised the Normal-regime value |
| `SupplyChainParams.partial_failure_min_frac` / `max_frac` | 0.0 / 0.5 | (no existing row — new) | Judgment call | On a failed delivery, the arrived fraction ~ Uniform(0, 0.5); no fitted failure-severity data exists for gallium logistics |
| `SupplyChainParams.emergency_lead_time_days` | 3 | (no existing row — new) | Judgment call | Faster than normal, deliberately not zero |
| `SupplyChainParams.emergency_cost_multiplier` | 1.5 | (no existing row — new) | Judgment call | Extra cost for expediting, applied on top of the replacement-cost curvature markup |
| `SupplyChainParams.replacement_cost_base_markup` | 0.03 | §6 Fixed bid spread (reinterpreted, same as Phase 1/2) | Judgment call | Coincides with `restock_markup_frac`/`bid_markup_frac` when available inventory ≥ safety stock |
| `SupplyChainParams.replacement_cost_curvature` | 2.0 | §3 Replacement-cost curvature parameter | Academic-model assumption | Capped (see "Bugs found" below) so worst-case markup is base + curvature (203% at these defaults), not unbounded |
| `AccountingParams.safety_stock_kg` (Phase 3, new field) | 60.0 | §3 Safety stock level | Judgment call | Deliberately a SEPARATE field from `restock_threshold_kg` (Phase 1's stub trigger, 50.0) so Phase 1/2 behavior is completely undisturbed by this addition — both instantiate the same register row at different values for different purposes |

### A deferred gap, flagged rather than built without documentation

The roadmap's Phase 3 "Add Supply-Chain Mechanics" list calls for
**channel-dependent (civilian vs. military-linked) shipment reliability**.
**This is NOT implemented.** The current register (Sections 1–6, as
delivered by Phase 0) has no military-linked demand or channel-reliability
rows at all. Building this split now would repeat exactly the mistake
Phase 1 made with symmetric jump sizes and an unregistered restock markup —
both caught and corrected (Section 7). This is logged here as an explicit,
deliberate gap: a proper register addendum (military-linked demand share,
channel-specific reliability figures, sourcing) needs to happen — likely
alongside Phase 4, which needs sector structure and `military_linked_share`
anyway — before this roadmap item is built, not smuggled in without it.

### Two real bugs found during Phase 3 integration testing, and how they were caught

Both were caught by actually running the full simulation end-to-end and
noticing the output was economically absurd — not by inspection alone. Both
are logged here per this project's standard of recording corrected findings
rather than quietly patching them.

1. **Unbounded convex replacement-cost markup.** The first implementation of
   `replacement_markup_frac` let the shortfall ratio `(safety_stock -
   available) / safety_stock` grow without bound for deeply negative
   available inventory. An early integration run produced markups over
   60,000% and a simulated terminal wealth of roughly **-$5.6 million** on a
   $50,000 starting position. Fixed by capping the shortfall ratio at 1.0,
   so the worst-case markup is `base_markup + curvature` (203% at the
   defaults) — severe, "emergency-tier" pricing, but not economically
   meaningless. See `src/supply_chain.py`'s `replacement_markup_frac`
   docstring.
2. **Reorder trigger placed new orders on every single day of a shortfall.**
   The first implementation triggered a new normal order whenever
   `available_kg() <= 0`, but `available_kg()` ignores shipments already in
   transit — so for the entire ~2-week lead time after the FIRST order was
   placed, the simulation kept placing duplicate orders every day, at
   markups near the (then-unbounded) cap. Fixed by switching to a standard
   inventory-theory **reorder point** — `safety_stock_kg + (lead-time
   demand)` — computed from already-registered quantities (`lead_time_days`,
   `safety_stock_kg`, the demand process's own arrival rate and order size),
   not a new free parameter. See `src/simulation.py`'s `_reorder_point_kg`
   docstring.
3. **(A related, non-bug accounting gap, fixed the same session.)** Cash
   paid for kg that was ordered but never arrived (a failed/partial
   delivery) was being debited from cash at order time but never subtracted
   from `realized_pnl()` or `mark_to_market_pnl()` — those metrics only
   count cost-of-goods-sold at the point of an actual sale, and kg that
   never arrives is never sold. `terminal_wealth()` (cash + inventory ×
   price) caught the loss correctly; the two P&L metrics did not, silently
   understating losses in any low-reliability scenario. Fixed by adding
   `DealerBook.record_lost_delivery_cost()`, called for the undelivered
   portion of every resolved shipment. See `src/accounting.py`.

After both fixes, a normal-reliability (95%) Phase 3 run on the Phase 1/2
demo seed produces terminal wealth of **~-$7,000** and mark-to-market P&L of
**~$3,800**. (These figures were updated again after the military/civilian
addendum below changed civilian unfilled-order treatment from "always
eventually backordered" to "lost sale" — losing some civilian sales volume
that the pre-addendum version never actually lost is the reason these
numbers are lower than an earlier draft of this section reported; the
change is a direct, expected consequence of the more realistic behavior,
not a new bug.) Terminal wealth is lower than Phase 1/2's instant-restock
baseline for the same reasons as before (conservative reorder-point
over-provisioning) plus, now, genuine lost civilian sales during any
physical-stock shortfall.

A stressed scenario (reliability dropped to 50%/30% civilian/military) produces a clearly
negative result (~-$445,000 to -$456,000 mark-to-market/terminal wealth, ~1,445kg
lost to failed deliveries) — the kind of directional sanity check this project leans on
in place of a backtest: worse supply reliability should make the dealer worse off, and it
now visibly does, by a plausible magnitude tied directly to the kg actually lost.

---

## 10. Military/civilian demand and channel reliability (addendum)

This section is added retroactively, ahead of Phase 4, specifically to unblock the
channel-dependent shipment reliability work that Phase 3's own build list calls for and
that Section 9 explicitly deferred for lack of register support. It is deliberately a
**simplified, aggregate, pre-sector** version of the roadmap's full military/civilian
design (which is per-sector and arrives properly in Phase 4). Every row below is written
so Phase 4 can later replace "aggregate" with "per-sector" without invalidating anything
built against these rows now.

| Parameter | Value | Meaning | Source type | Justification | Sensitivity |
|---|---|---|---|---|---|
| Military-linked demand share (aggregate, pre-sector) | 15% | Fraction of ALL customer orders tagged military-linked, before Phase 4 splits this by sector | Judgment call | A single aggregate placeholder standing in for Phase 4's per-sector shares (Defense & Aerospace highest, others lower but nonzero, per phase0_research_notes.md §3); chosen as a plausible blended average across a hypothetical sector mix, not fitted | High |
| Military-linkage assignment mechanism | Per-order Bernoulli draw, p = military-linked share | Whether each individual order (not each customer) is tagged military-linked | Model assumption | Matches the existing per-shipment Bernoulli machinery already used for delivery reliability (src/supply_chain.py); avoids persistent customer-identity tracking, which is out of scope until Phase 4 at the earliest | Medium |
| Civilian-channel shipment reliability | Equal to the existing §2 Normal-regime shipment reliability (95%) | Probability a civilian-channel shipment arrives successfully | Judgment call, informed by research (reused from §2) | No change from Section 9's supply chain — civilian is the "default" channel Phase 3 already modeled | Medium |
| Military-channel reliability discount | -20 percentage points vs. civilian (→ 75% at current civilian=95%) | Extra reliability penalty applied only to military-linked shipments | Scenario assumption, informed by the real 2024–2025 export-control structure (phase0_research_notes.md §2: military end-use restrictions can stay active even after general licensing eases) | Chosen to be a material, visible gap without implying near-total failure; exact magnitude is a judgment call pending Phase 9 sensitivity | High |
| Unfilled order treatment | Civilian: lost sale (rejected, matches Phase 1/2 behavior). Military-linked: rolls into Committed Inventory as a backlog, with a per-day penalty cost, rather than disappearing | Whether a rejected order is lost or persists as a liability | Judgment call | Military-linked orders more plausibly represent standing contracts (procurement cycles, phase0_research_notes.md §3) than discretionary spot demand that simply walks away | High |
| Backlog penalty cost | 0.5% of order value per day outstanding | Daily holding-cost-equivalent penalty accrued while a military-linked backorder remains unfulfilled | Judgment call | No public data on gallium backlog/contract-penalty terms exists; chosen to be small enough not to dominate P&L on its own but large enough to make prolonged backlog visibly costly over weeks, consistent with the project's general practice of avoiding pathologically large or small placeholder magnitudes (see Section 9's markup-cap lesson) | High |

### Explicit scope of this addendum

- This is NOT Phase 4. There is still no sector structure (Semiconductors, Defense &
  Aerospace, Telecommunications, Solar), no per-sector military-linked share, no Hawkes
  demand, and no demand-elasticity difference between military and civilian orders (the
  register's future Phase 4 "Military demand price-sensitivity" row is not built here —
  military-linked orders in this addendum face the exact same willingness-to-pay
  distribution as civilian orders; only their SHIPMENT RELIABILITY and UNFILLED-ORDER
  TREATMENT differ). Without a price-sensitivity difference, a pricing-only policy has no
  way to differentially protect military demand through the ask price alone — which is
  precisely the gap this project's second core research question (Phase 5/7/9) is built to
  probe, so it is being surfaced here rather than hidden.
- The 15% aggregate share and the -20pp reliability discount are both flagged High
  sensitivity and are explicit candidates for the Phase 9 sweep — read any headline
  military-vs-civilian comparison in this project as scoped to these exact figures, not as
  a general finding about gallium markets.

### A methodological caveat found while building the headline comparison

`Simulation.run()`'s `military_fill_rate` measures whether an order was ACCEPTED
(immediate sale, backordered, or emergency-backordered) — NOT whether the promised
gallium was ever actually delivered. Because this project's "never decline a
military-linked commitment" simplification (src/simulation.py) means every military
order eventually gets *some* fulfillment path, `military_fill_rate` stays essentially
flat (~21%, matching the underlying price-vs-willingness-to-pay economics) regardless of
supply reliability — it does not, by itself, show the protection mechanism at work.

A second metric, `military_kg_delivery_rate` (fraction of committed military kg actually
delivered by the end of the run), was added to check this more honestly. At a 252-day
horizon it converges to ~100% in every reliability scenario tested — the backlog always
eventually clears, given enough time and enough emergency reordering. This is *also* not
the differentiator.

**What actually differentiates scenarios, verified across 50 matched seeds at three
reliability levels (Normal 95%/75%, Delayed 60%/40%, Severe 25%/10% civilian/military,
lead time 21 days, see the stress-test parameters logged below) is the COST of
maintaining that 100% eventual-delivery guarantee:**

| Scenario | Civilian fill rate | Military kg delivery rate | Mean backlog penalty paid | Mean mark-to-market P&L |
|---|---|---|---|---|
| Normal (95%/75%) | 19.8% | 100% | $341 | -$165,007 |
| Delayed (60%/40%) | 19.7% | 100% | $379 | -$403,979 |
| Severe (25%/10%) | 18.9% | 100% | $496 | -$862,122 |

Civilian fill rate degrades only mildly (19.8% → 18.9%) because civilian orders are
simply lost when physical stock runs short — there's no queue for them to wait in.
Military delivery is *always eventually guaranteed* at these parameters (this project's
simplification bites here — a real dealer might eventually give up on an unfulfillable
commitment; this one never does). The economically meaningful result is that guaranteeing
that 100% comes at a monotonically rising P&L cost as the supply chain degrades — a small,
scoped, honest version of this project's second core research question ("what does
protecting military-critical supply cost in dealer P&L?"), well short of Phase 5's full
scarcity-adjusted policy comparison but a real, verified first data point toward it.

**Stress-test parameters used to produce the table above** (deliberately more extreme
than this addendum's own defaults, chosen to force genuine physical scarcity — the
default calibration's reorder-point logic over-provisions so heavily that scarcity
barely ever binds; see Section 9's over-accumulation note, which this table reconfirms
and sharpens): `initial_inventory_kg=25, restock_amount_kg=15, safety_stock_kg=10,
lead_time_days=21, arrival_rate_per_year=250, military_linked_share=0.15`. These are
demo/stress-test values for this table specifically, not new defaults — logged here for
reproducibility, not written into `AccountingParams`/`SupplyChainParams`.

---

## 11. Phase 4 implementation values (regimes, sectors, Hawkes demand, military elasticity)

This section instantiates concrete values for the §1/§2/§4 rows left as "—" placeholders,
and adds new rows for what Phase 4 introduces that no earlier section anticipated:
per-sector military-linked shares, military demand price-sensitivity, and per-regime
military-channel reliability (the Section 10 addendum only ever specified a single
Normal-regime military discount).

### 11.1 Regime-dependent price jump parameters (instantiating §1)

| Regime | Jump intensity multiplier (vs. Normal) | Jump size multiplier (vs. Normal) | Source type | Justification |
|---|---|---|---|---|
| Normal | 1.0 | 1.0 | Judgment call | Baseline — matches `PriceProcessParams` defaults (§1, §7) |
| Delayed | 2.0 | 1.3 | Judgment call | Licensing-requirement period (2023): more frequent, moderately larger jumps than calm baseline, well short of Severe |
| Severe | 6.0 | 2.0 | Judgment call, informed by real data | §1's existing "substantially elevated" Severe-regime row, now a concrete multiplier; matches the clustered, discrete repricing pattern in phase0_research_notes.md §2 |
| Recovery | 2.5 | 1.2 | Judgment call | Above Normal (the register's own framing: "a pause, not a resolution," phase0_research_notes.md §2) but below Delayed — some residual repricing risk as the market unwinds |

### 11.2 Regime-dependent shipment reliability (instantiating §2, and extending §10 to all four regimes)

| Regime | Civilian reliability | Military reliability | Civilian-military gap | Source type | Justification |
|---|---|---|---|---|---|
| Normal | 95% | 75% | 20pp | Judgment call (civilian: real §2 row; military: §10's -20pp) | Unchanged from §2/§10 |
| Delayed | 70% | 45% | 25pp | Judgment call | Civilian is §2's existing row; military discount widened slightly — early licensing friction plausibly hits military end-use scrutiny somewhat harder even before a full ban |
| Severe | 40% | 15% | 25pp | Judgment call, informed by real data | Civilian is §2's existing row; military discount widened further, informed by phase0_research_notes.md §2's point that a military end-use ban can remain active even during a general licensing regime |
| Recovery | 75% | 40% | 35pp | Judgment call | Civilian is §2's existing row; military lags well behind — phase0_research_notes.md §2 explicitly notes civilian licensing has historically eased before military-end-use restrictions, so a RECOVERING civilian channel actually WIDENS the gap versus a still-lagging military channel, rather than narrowing it |

**A correction, caught by this project's own test suite:** an earlier draft of this row
claimed in prose that "Severe is where the channel gap should be starkest," but the
actual chosen numbers make Recovery's gap (35pp) wider than Severe's (25pp) — internally
inconsistent. Rather than force the numbers to match the sloppier claim,
`tests/test_regimes.py::test_severe_and_recovery_both_show_wider_reliability_gaps_than_normal`
was written to check the economically correct, defensible property instead: both Severe
AND Recovery show wider gaps than Normal, and Recovery's can legitimately exceed Severe's,
because "civilian recovers faster than military" and "military ban persists during the
worst of the disruption" are two different, complementary reasons for a wide gap, not one
single "severity" axis where Severe must always be the extreme.

### 11.3 Regime transition matrix (register §2: "to be specified in regimes.py")

Daily self-transition probabilities (implying an expected regime duration via
`1/(1-p_self)` at a 252-day year convention), and the off-diagonal transitions:

| From \ To | Normal | Delayed | Severe | Recovery |
|---|---|---|---|---|
| Normal | 0.997 | 0.003 | 0.000 | 0.000 |
| Delayed | 0.010 | 0.980 | 0.010 | 0.000 |
| Severe | 0.000 | 0.000 | 0.985 | 0.015 |
| Recovery | 0.005 | 0.000 | 0.003 | 0.992 |

Implied expected durations: Normal ~333 days, Delayed ~50 days, Severe ~67 days,
Recovery ~125 days. Judgment call, no fitted multi-state data exists (only one real
historical escalation cycle to draw qualitative shape from, per §2's own row). Chosen to:
(a) make Normal the by-far-most-persistent state, (b) only allow Severe to be entered via
Delayed, never directly from Normal (matching the real 2023 licensing → 2024 ban
sequence), (c) let Recovery relapse into Severe (small probability) rather than only ever
improving, since phase0_research_notes.md §2 explicitly frames the 2025 suspension as
conditional and revocable, not a clean resolution.

### 11.4 Sector definitions (instantiating §4)

| Sector | Relative arrival rate (orders/year) | Order size mean (kg) | WTP spread (frac) | Military-linked share | Source type |
|---|---|---|---|---|---|
| Semiconductors | 140 | 20 | 0.04 | 0.10 | Judgment call |
| Telecommunications | 70 | 22 | 0.045 | 0.12 | Judgment call |
| Defense & Aerospace | 25 | 35 | 0.08 | 0.70 | Judgment call |
| Solar / Clean Energy | 40 | 18 | 0.06 | 0.05 | Judgment call |

Rankings (Semiconductors highest frequency, Defense & Aerospace highest WTP dispersion
and highest military share, Solar most price-sensitive) directly match the register's
existing §4 "Base order-arrival rate per sector" and "Sector willingness-to-pay ranking"
rows and phase0_research_notes.md §3's qualitative sector descriptions. Combined arrival
rate (140+70+25+40 = 275/year) is close to but not identical to the pre-sector aggregate
`DemandParams.arrival_rate_per_year` (250, §7) — the small increase is a judgment call,
not a calibration target: sector totals were built up independently per sector rather
than forced to sum to the old aggregate number.

### 11.5 Military-linked share now per-sector, superseding §10's aggregate figure

§10 logged a single aggregate `military_linked_share = 0.15` as an explicit placeholder
"standing in for Phase 4's per-sector shares." Per this file's own rule 4 ("do not delete
superseded rows — strike through or annotate them"): **§10's aggregate 15% figure is
superseded by the per-sector shares in §11.4 above**, effective wherever
`src/demand.py`'s new sector-based order flow is used. The old aggregate
`DemandParams.military_linked_share` field and the non-sector `PoissonOrderFlow` class
remain in code, unchanged, for backward compatibility with every Phase 1–3 test — they
are simply no longer what Phase 4 mode actually uses.

### 11.6 Military demand price-sensitivity (new — the register's previously-flagged gap)

| Parameter | Value | Meaning | Source type | Justification |
|---|---|---|---|---|
| Military WTP spread multiplier | 2.5× the sector's civilian WTP spread | Military-linked orders' willingness-to-pay is drawn from a WIDER distribution than civilian orders in the same sector | Judgment call, informed by procurement-cycle literature (phase0_research_notes.md §3) | A wider WTP spread means a flatter execution-probability-vs-price curve: military orders are less likely to walk away as price rises, without changing their AVERAGE price sensitivity direction |
| Military WTP mean shift | +3% above the sector's civilian mean WTP | Military-linked orders are centered slightly higher, not just wider | Judgment call | Reflects that procurement-driven demand is somewhat less price-anchored to the current spot quote than discretionary civilian demand |

This is the exact gap §10 flagged: *"Without a price-sensitivity difference, a
pricing-only policy has no way to differentially protect military demand through the ask
price alone."* Phase 4 closes it. Whether this elasticity difference alone (without
Phase 5's priority overlay) meaningfully changes the military-vs-civilian fill-rate gap
is an open, testable question — see the Phase 4 mastery checkpoint in the README, not
assumed here.

### 11.7 Hawkes process parameters (instantiating §4)

| Parameter | Value | Source type | Justification |
|---|---|---|---|
| Hawkes excitation strength (alpha), Normal | 0.05 | Model assumption | Low branching ratio in calm conditions — one order barely raises the odds of another |
| Hawkes excitation strength (alpha), Severe | 0.6 | Model assumption | §4's own row: "moderate-to-high during Severe regime" — a single urgent order meaningfully raises near-term arrival intensity |
| Hawkes decay rate (beta) | 8.0 / year (≈ 32-day half-life) | Model assumption | §4's own wording: influence fades "over a period of days to weeks," not instantly or permanently |

Excitation strength is regime-dependent (linearly interpolated between the Normal and
Severe values above, keyed to the same four-regime multiplier pattern as §11.1) — panic
clustering should be stronger precisely when scarcity fears are already elevated, per
§4's own justification for this row.

---

## 12. Phase 5 implementation values (scarcity-adjusted policy + priority overlay)

### 12.1 The five new premiums (instantiating §5's "Scarcity-premium functional form" row, and adding four siblings it didn't cover)

All premiums are additive dollar amounts added to the standard Avellaneda-Stoikov
reservation price (`src/policies/avellaneda_stoikov.py`), which then flows through
unchanged into `ask = reservation_price + spread/2`. Each is capped to avoid repeating
Phase 3's unbounded-convexity bug (see §9) — every ratio-based term below is explicitly
clamped before being raised to a power.

| Premium | Formula | Parameter | Value | Source type | Justification |
|---|---|---|---|---|---|
| Scarcity premium | `mid × γ_scarcity × min(1, shortfall/safety_stock)²` where shortfall = max(0, safety_stock − available_kg) | `scarcity_gamma` | 0.05 | Academic-model assumption (§5's existing row) | Convex, capped at `mid × γ_scarcity` (≈5% of price) — same capping lesson as §9's replacement-cost fix |
| Replacement-cost premium | `mid × pass_through × (replacement_markup_frac − base_markup)` | `replacement_cost_pass_through` | 0.15 | Judgment call | Only partially passes the supply chain's own nonlinear replacement cost (§9) through to the customer quote — a dealer eating some of its own restocking cost is more realistic than 100% pass-through |
| Shipment-risk premium | `mid × γ_shipment × (1 − civilian_reliability)` | `shipment_risk_gamma` | 0.10 | Judgment call | Uses the CURRENT (possibly regime-modulated, §11.2) civilian reliability directly — a policy quoting in a Severe regime should demand more compensation for unreliable incoming supply, without needing its own separate regime lookup |
| Commitment premium | `mid × γ_commitment × min(3, committed_kg/safety_stock_kg)` | `commitment_gamma` | 0.03 | Judgment call | Capped at 3× safety stock's worth of commitments — protects against unbounded growth if backlog balloons |
| Regime premium | `mid × γ_regime × regime_severity` (regime_severity ∈ [0,1]: Normal=0, Delayed=Recovery=0.5, Severe=1.0) | `regime_gamma` | 0.08 | Judgment call | A direct, bounded regime signal, independent of the other four (which each already react to regime indirectly through reliability/scarcity) — captures the register §2 "regime premium" behavior the roadmap calls for explicitly |

At the defaults above, worst-case combined premium (all five maxed simultaneously) adds
roughly `mid × (0.05 + 0.15×2.00 + 0.10 + 0.03×3 + 0.08) ≈ mid × 0.62` — a severe,
"scarcity-tier" markup, bounded rather than unbounded, deliberately smaller than the raw
uncapped replacement-cost curve itself (§9) since a dealer eating some of that cost is
part of the point of `replacement_cost_pass_through` < 1.0.

### 12.2 Priority-allocation overlay

| Parameter | Value | Meaning | Source type | Justification |
|---|---|---|---|---|
| Priority-overlay strictness (p) | Continuous, 0–1 (default 1.0 when the overlay is constructed at all — callers choose to enable it) | 0 = no overlay, 1 = hard DPAS-style mandate, values between = probabilistic queue preference | Model assumption | Matches the roadmap's own specification: one parameter unifying the on/off ablation and the Phase 9 sensitivity sweep |

**Implementation note on "reactive, not proactive" and what "contested" means in this
codebase:** the roadmap specifies the overlay activates "at the moment of a fill decision
when available inventory can't cover every order competing for it in that period." In
this project's daily-timestep architecture, contention is checked once per day: if more
than one order arrives on the same day AND at least one is military-linked and at least
one is civilian, a single Bernoulli(p) draw decides whether military-linked orders are
attempted first that day (winning any physical stock that can't cover everyone). This is
a simplification of true pairwise/continuous-time contention (the roadmap's own language)
to fit a discrete daily loop — logged here as a scoping decision, not hidden. On days with
only one order, or with orders from only one channel, there is nothing to contest and the
overlay has no effect, matching "reactive, not proactive" exactly: quoting is never
changed by the overlay, only the fill ORDER on contested days.

### 12.3 Pre-registered ablation hypotheses (per the roadmap's own requirement — written before Phase 9 runs any ablation)

| Component | Behavior captured | Expected consequence if removed |
|---|---|---|
| Scarcity premium | Protects scarce inventory | More stockouts / lower available_kg on average |
| Replacement-cost premium | Reflects expensive replenishment | Underpricing during disruptions |
| Shipment-risk premium | Discounts unreliable incoming supply | Excess reliance on pipeline inventory that may not arrive |
| Commitment premium | Protects inventory already owed | Over-selling relative to standing commitments |
| Regime premium | Direct compensation for regime severity | Quotes under-react to regime changes not already captured by the other four premiums |
| Priority-allocation overlay (p=1 vs p=0) | Guarantees military-tagged orders are filled first on contested days | Military-linked fill rate falls toward the civilian rate on contested days specifically — tests whether pricing alone (Phase 4's elasticity effect) was already sufficient |

These are written down now, before any ablation is run, so that Phase 9's results are
read as confirming or overturning a stated prior — not as post-hoc pattern-matching.

### 12.4 Findings from Phase 5 integration testing, logged honestly

**A real, non-trivial result:** across 40 matched seeds, the scarcity-adjusted policy
underperforms the naive fixed-spread baseline under CALM (Phase 3, no regime spikes)
conditions (mean mark-to-market P&L ≈ -$110,835 vs. fixed-spread's ≈ +$48,611) — but
becomes the BEST of the three tested policies under full Phase 4 regime stress
(≈ -$109,545 vs. fixed-spread's ≈ -$37,803 and plain AS's ≈ -$572,992). Plain AS is worst
in both conditions, consistent with Phase 2's already-documented thin-margin finding
compounding under stress. This flips the Phase 2 story specifically under disruption,
which is exactly the condition this project's core research question is about — not a
claim that scarcity-adjustment is unconditionally better.

**The priority overlay's aggregate fill-rate effect is small at tested calibrations, even
though the underlying mechanism is verified correct.** Confirmed structurally (unit and
integration tests: `p=1` always prioritizes military on contested days, `p=0` never does,
intermediate `p` prioritizes probabilistically at roughly the expected rate) — but the
AGGREGATE effect on civilian/military fill rates across a full simulation is small
(civilian fill rate moves from ~32.85% at p=0 to ~32.78% at p=1 in the stress scenario
used for `phase5_overlay_strictness_frontier.png`). This is because genuine SAME-DAY
cross-channel contention (both a civilian and a military order arriving on the identical
day, with physical stock insufficient for both) is a relatively rare subset of all
fill/reject decisions even under stress — most outcomes are driven by price economics
(ask vs. willingness-to-pay) or by single-channel days, not by which of two same-day
orders gets processed first. This is the SAME underlying mechanism as Section 9's
over-provisioning finding, resurfacing here: the reorder-point's conservative buffer keeps
physical stock high enough, often enough, that order-level contention rarely binds.
Reported honestly rather than tuned until it produced a more dramatic chart.

**Where this leaves the research question:** military-linked orders already fill at a
substantially higher rate than civilian ones (Phase 4's finding: ~47.5% vs. ~18.3%,
register Section 11) through PRICING ALONE (the elasticity mechanism). This addendum
finds the priority overlay adds comparatively little on top of that at current
calibrations — but this is a single-point, non-statistical observation (40 seeds, one
parameter set), not a general claim. Phase 9's proper sensitivity sweep across `p`,
safety-stock sizing, and the military elasticity parameters together is what should
determine whether this holds more broadly or is itself calibration-dependent.

---

## 13. Phase 6 implementation values (dynamic-programming policy)

Phase 6 is explicitly flagged in the roadmap as an advanced phase whose full build is
future work relative to the paper's core scope. Built here anyway, at a deliberately
CONTAINED scope: the required toy Bellman prerequisite, plus a real but explicitly
simplified finite-state DP policy solved via backward induction — not a faithful
re-derivation of the full simulation's dynamics, which would defeat the entire point of
finite-state DP being a tractable *approximation* (see the Phase 6 mastery checkpoint).

### 13.1 Discretization (new parameters — the DP's own internal, simplified world model)

| Parameter | Value | Meaning | Source type | Justification |
|---|---|---|---|---|
| Inventory bins | 5 bins, edges at [0, 0.5, 1.0, 2.0, 4.0] × safety_stock_kg | Discretized inventory state for the DP's state space | Model assumption | Coarse enough to keep the state space tractable (register's own curse-of-dimensionality caution), fine enough to distinguish "critical," "low," "normal," "high," "very high" |
| DP periods | 1 per simulated day, `T_dp = n_steps` at construction | Discretized time state | Model assumption | Matches the actual simulation's daily granularity directly, avoiding an extra time-bucket rounding approximation |
| Action markups | aggressive=1%, normal=4%, defensive=10%, stop=100%, emergency_purchase=4% (+ triggers a real order) | The five roadmap-specified actions, each mapped to a concrete ask markup | Judgment call | `normal` matches other policies' baseline (register §6); `stop`'s 100% markup is chosen to be far outside any registered WTP dispersion (§7's 5%), making a sale in that state a near-impossibility rather than literally guaranteed-zero (kept a genuine action outcome rather than a hard-coded refusal) |
| Simplified fill-probability model | `P(Z ≥ markup/wtp_spread_frac)`, reusing §7's `wtp_spread_frac=0.05` | The DP's own internal (not the real simulation's) model of how markup affects fill probability | Model assumption, reusing an existing register value | Same closed-form logic already used to sanity-check Phase 1's demo fill rate (README) — reused here for internal consistency, not re-derived |
| Per-period restock probability | 15%/day, independent of action (100% if action = emergency_purchase) | The DP's own simplified model of replenishment, decoupled from the real supply-chain mechanics (Phase 3) | Judgment call | The DP cannot know the real supply chain's stochastic lead times inside a tractable Bellman recursion — this is a deliberate abstraction, not an oversight |
| Scarcity penalty | -5 (reward units) for ending a period in inventory bin 0 | Represents stockout cost inside the DP's simplified reward | Judgment call | Same qualitative role as the scarcity premium (§12.1), reduced to a single constant since the DP's reward function must stay simple enough for exact backward induction |
| Emergency purchase cost | -8 (reward units), applied whenever action = emergency_purchase | Represents the real cost of an emergency order (register §9's emergency_cost_multiplier) inside the DP's simplified reward | Judgment call | Chosen to be smaller than the scarcity penalty's potential MULTI-PERIOD cost of staying at bin 0, so the DP has a genuine incentive to sometimes pay it |
| Terminal value | `bin_index × 6` (reward units) | Value assigned to ending inventory at the DP's horizon | Model assumption | Encodes "ending with more inventory is worth more," the same principle as Expected/Physical inventory's economic value (§3) — magnitude chosen (via the toy example, §13.2) to be large enough that preserving high inventory can beat immediate-sale reward near the horizon, illustrating genuine dynamic (not myopic) behavior |

### 13.2 Toy Bellman example (the roadmap's required prerequisite, hand-derived)

Before the real DP was built, a 3-state (Low/Medium/High inventory), 2-action (Sell/Hold),
2-period toy problem was solved BY HAND (see `src/policies/dp_toy_example.py`'s module
docstring for the full derivation) and then confirmed to match a programmatic
backward-induction solver bit-for-bit. Values chosen specifically so that Sell is optimal
in every state except High inventory near the horizon, where Hold wins — because a large
terminal value (30) for ending at High inventory outweighs Sell's larger immediate reward,
demonstrating genuine non-myopic behavior (a purely greedy policy would pick Sell
everywhere, since it has the higher immediate reward in every single state).

### 13.3 Findings from Phase 6 integration testing, logged honestly

**Discretization loss, observed directly, not just described abstractly.** At this
project's default calibration, `aggressive`, `defensive`, and `stop` are essentially
NEVER selected by the solved policy — `normal` dominates them in raw expected-margin
terms (a markup 4× higher than `aggressive`'s outweighs `aggressive`'s roughly 2×-higher
fill probability), and `defensive`/`stop`'s only real benefit (avoiding further depletion)
provides **zero modeled value at the lowest inventory bin**, because the transition model
floors at bin 0 regardless of action — there is no "more depleted than empty" state for a
5-bin discretization to distinguish. This is exactly what the roadmap's own mastery
checkpoint asks about ("what discretization loses"): the real difference between
"just below safety stock" and "deeply negative available inventory" (Section 3's
`available_kg`, which is explicitly allowed to go negative) is invisible to this DP's
5-bin state space. Only `normal` and `emergency_purchase` are ever chosen in practice —
logged here rather than silently re-tuned until the full action space looked busier.

**The DP does not outperform the simpler scarcity-adjusted policy at these calibrations.**
Across 30 matched seeds under full Phase 4 regime stress: fixed-spread ≈ **-$64,881**
(σ≈358k), inventory heuristic ≈ **-$115,348** (σ≈345k), plain AS ≈ **-$645,522** (σ≈964k,
worst — consistent with Phase 2's already-documented thin-margin finding compounding
under stress), scarcity-adjusted AS ≈ **-$114,264** (σ≈111k, by far the LOWEST variance
of any policy), dynamic programming ≈ **-$181,892** (σ≈604k). The DP is better than plain
AS but worse than both the fixed-spread baseline and the scarcity-adjusted policy on
average, and far more volatile than scarcity-adjusted AS specifically. This is plausibly
explained by the DP's own documented limitations (Section 13.1): it plans against a
FIXED reference price and a simplified internal demand/restock model that has no
knowledge of the real simulation's jump-diffusion prices, Hawkes clustering, or the
competing scarcity-adjusted policy's own premiums — the gap between "the world the DP was
solved for" and "the world it actually runs in" (this module's own stated central
limitation) shows up directly in the numbers, not just in theory.

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
