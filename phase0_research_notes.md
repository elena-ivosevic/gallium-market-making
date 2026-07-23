# Phase 0 — Research Notes

This document summarizes the public research used to ground `assumptions_register.md`.
It is a working reference, not a citation-complete literature review. Anywhere a number
in the assumptions register is labeled "Real data," the supporting figure is summarized here.

## 1. Gallium production concentration

- China accounts for roughly **98–99% of world primary (low-purity) gallium production**,
  a level of concentration reported consistently by the USGS Mineral Commodity Summaries,
  CSIS, and industry trackers (Statista, Geopolitical Monitor). Estimates cluster tightly
  in the 98–99% range depending on year and methodology, so the project treats **~98%** as
  the working point estimate with a note that it has been as high as 99% in USGS data.
- Global primary gallium production is small in absolute terms — on the order of a few
  hundred to roughly 750 metric tons per year worldwide (713 t in 2023 per industry
  trackers) — which is why the market is thin, illiquid, and easily disrupted by a single
  country's policy decisions.
- Gallium is not mined directly. It is recovered almost entirely as a **byproduct of
  bauxite (aluminum) refining**, with smaller recovery from zinc-processing residues. This
  matters for the model: gallium supply cannot simply "ramp up" in response to price the
  way a primary-mined commodity can, because production is tied to decisions made in a
  different industry (aluminum refining) for different reasons.
- Outside China, primary low-purity producers are limited to Japan, South Korea, and
  Russia in small volumes. Former producers (Germany, Hungary, Kazakhstan, Ukraine) have
  ceased or reduced primary production, though new capacity (e.g., Eurasian Resources
  Group's Kazakhstan project, targeted for 2026) is emerging slowly and is not yet
  material to global supply.

## 2. Export-control timeline (China)

The controls have escalated in discrete steps rather than as a single event, which is why
the project models **regimes** (Normal / Delayed / Severe / Recovery) rather than a single
shock:

- **July 2023:** China introduced licensing requirements for gallium and germanium exports
  — the first restriction, widely described as a "warning shot" rather than a full
  cutoff.
- **December 2024:** China's Ministry of Commerce (MOFCOM Document No. 46) escalated to an
  explicit **export ban targeting the United States**, creating a presumption of denial
  for gallium exports to U.S. end users.
- **January 2025:** Gallium *extraction technologies* (not just the metal itself) were
  added to China's export-control list, restricting the transfer of know-how as well as
  material.
- **May 2025:** Cross-departmental enforcement action against smuggling and transshipment
  of controlled minerals.
- **November 2025:** Following a Trump–Xi meeting, China suspended the U.S.-specific
  gallium export prohibition for one year (through **November 27, 2026**), while keeping
  the underlying licensing regime for gallium, germanium, and antimony in place, and
  without lifting the ban on supplying U.S. military end users.
- **As of mid-2026:** Reporting indicates the suspension is a **pause, not a resolution**
  — licenses are granted at China's discretion and can be slow-walked, and gallium prices
  outside China had reportedly surged to record levels (~$1,850/kg by April 2026 per
  Fastmarkets, over 200% higher than the start of 2025), while prices inside China stayed
  comparatively stable, producing a bifurcated market.

This is the empirical basis for the project's **regime-switching** structure: real
disruptions have arrived as a sequence of escalating policy steps with a partial,
conditional, revocable "recovery," not as one clean shock followed by a full return to
normal.

## 3. Gallium end uses (why sector demand differs)

- **Semiconductors:** Gallium arsenide (GaAs) and gallium nitride (GaN) compounds are used
  in RF/power semiconductors. Industry estimates cited in supply-chain analyses put on the
  order of 8–12 specialized GaAs RF integrated circuits in each 5G base station, with
  millions of base stations deployed worldwide — illustrating a large, relatively
  price-insensitive, high-value-per-kilogram customer base.
- **Defense and aerospace:** GaN and GaAs are used in radar (AESA), electronic warfare, and
  satellite systems. This sector is characterized in public commentary as high
  willingness-to-pay and high urgency (mission-critical, low substitutability, national
  security priority), but low order frequency and often long lead times set by
  procurement cycles rather than spot markets.
- **Telecommunications:** Overlaps with semiconductor RF demand (5G infrastructure);
  treated as a distinct sector in the model because build-out schedules and urgency
  differ from general semiconductor manufacturing.
- **Solar / clean energy:** Gallium is used in some high-efficiency and multi-junction
  photovoltaic cells and in certain thin-film technologies. This is treated as a
  smaller-volume, more price-sensitive sector relative to defense.

Sector-level order-arrival rates, order sizes, and willingness-to-pay are **not** derived
from proprietary sales data (none is available); they are **judgment calls** informed by
the qualitative sector descriptions above, and are labeled as such in the assumptions
register.

## 4. Physical commodity-market characteristics used to justify model choices

- Small annual volumes (hundreds of metric tons) + concentrated production (one country)
  + byproduct-only supply (no independent production response to price) together explain
  why gallium behaves less like a liquid, continuously-traded financial asset and more
  like a **negotiated, thinly traded physical market** — motivating jump-diffusion prices,
  regime switching, and an inventory-centric (rather than pure price-discovery) dealer
  model.
- Reported price behavior (relatively flat prices for long stretches, punctuated by sharp,
  policy-driven jumps of 11%–200%+ over months) is consistent with a **jump-diffusion**
  rather than **pure geometric Brownian motion** characterization — see Mastery Checkpoint
  below.

## 5. Modeling literature (why these specific tools)

- **Avellaneda–Stoikov (2008)** market making: provides a closed-form, inventory-aware
  reservation price and optimal bid/ask spread under a risk-aversion parameter and a
  finite trading horizon. Chosen as the project's baseline "principled" quoting model
  because it is the standard, well-understood starting point in the market-making
  literature, and because its assumptions (single tradable asset, continuous
  re-quoting, inventory penalty) can be explicitly extended/critiqued for a physical
  commodity.
- **Jump-diffusion models** (e.g., Merton-style jumps layered on a mean-reverting
  diffusion): standard way to represent rare, large, exogenous shocks (like an export
  ban announcement) that a continuous diffusion process cannot generate with realistic
  probability.
- **Poisson processes**: standard baseline for "independent, memoryless" order arrivals —
  used as the starting point in Phase 1 before critique.
- **Hawkes processes**: self-exciting point processes in which one event temporarily
  raises the probability of subsequent events. Widely used in market microstructure
  literature to model order-flow clustering and, more broadly, "panic" or contagion-style
  arrival patterns — chosen here because a single urgent customer order during a shortage
  plausibly triggers other customers to order urgently too (panic buying), which a plain
  Poisson process cannot represent.
- **Markov regime-switching models**: standard way to represent a small number of
  qualitatively distinct market states (Normal/Delayed/Severe/Recovery) with persistence
  and stochastic transitions between them — a natural fit for the discrete, escalating
  policy-driven history described in Section 2.

## Mastery Checkpoint — answers to hold in memory (not to read aloud)

**Q1. Why might gallium prices be better modeled with jumps than with plain geometric
Brownian motion (GBM)?**

GBM assumes continuously compounding, log-normally distributed returns with no sudden
discontinuities — it is built for assets that trade often enough that information gets
absorbed gradually. Gallium's real price history does not look like that: prices sit
roughly flat for extended periods and then move sharply within days to months around
discrete policy events (export-control announcements, bans, suspensions). A pure GBM
would need an implausibly high constant volatility to generate those moves with any
reasonable probability, which would in turn make it wildly overpredict day-to-day noise
in calm periods. A jump-diffusion model separates the two regimes explicitly: low
continuous volatility most of the time, plus a rare, sized "jump" term whose intensity
and magnitude can itself depend on the geopolitical regime. That matches the observed
pattern (long calm stretches, punctuated policy-driven repricing) far better than a single
constant-volatility diffusion.

**Q2. Why might panic buying be better represented by a Hawkes process than by a standard
Poisson process?**

A standard Poisson process assumes order arrivals are independent and memoryless — one
customer's order tells you nothing about the probability of the next. But panic buying is
explicitly a contagion phenomenon: one customer placing an urgent order (because they
believe supply is at risk) is a signal that raises the odds other customers do the same,
and that elevated ordering probability decays over time rather than resetting instantly.
A Hawkes process captures exactly this: a baseline arrival rate plus a "self-exciting"
term that temporarily spikes intensity after each event and decays afterward. This
produces the clustering (bursts of orders close together in time) that panic buying
displays and that a memoryless Poisson process cannot generate by construction.
