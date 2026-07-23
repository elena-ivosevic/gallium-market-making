# README Honesty Paragraph

*This text is written to be dropped verbatim (or near-verbatim) into the top of the main
project `README.md`, above any results, figures, or performance claims. It is written
before the model exists so that it constrains what can later be claimed, rather than
being written after the fact to explain away weak results.*

---

> **What this project is, and what it is not.**
>
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
> `docs/assumptions_register.md` as Real data, Analogous-market estimate,
> Academic-model assumption, or Judgment call, and that label is the honest description
> of its evidentiary weight.
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
> export controls) is offered as a **qualitative plausibility check** — does the model
> move in the expected direction when a similar shock is simulated? — and not as a
> calibration exercise, and not as a claim that the model predicts, reproduces, or
> explains actual historical prices, shortages, or industrial outcomes. Phase 7's
> sector-level results in particular describe the behavior of **simulated customers**
> under assumed demand and inventory parameters; they are not estimates of real
   industrial production, real economic loss, or real company-level impact.
>
> This project is a decision-modeling and market-microstructure exercise built on
> defensible, clearly labeled assumptions — not a validated forecasting or trading
> system for the physical gallium market.

---

### Why this is written now, in Phase 0

Writing this paragraph before any model code exists is intentional. Its purpose is to
put a ceiling on the claims the rest of the project is allowed to make. If, later, a
result "feels" too strong to be justified by hand-specified scenario assumptions, that is
a signal the result is being over-interpreted — not a signal to loosen this paragraph.
