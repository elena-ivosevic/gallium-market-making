"""
sector_stress_test.py
======================

Phase 7 deliverable: Sector Transmission Stress Test.

REQUIRED FRAMING (state this before showing anyone a result from this module)
----------------------------------------------------------------------------------
These outputs describe the behavior of SIMULATED customers under assumed demand
and inventory parameters. They are NOT estimates of realized industrial
production or economic damage. A true input-output economic study uses
observed prices, quantities, and economic tables to estimate real effects on
real firms; this project instead examines how simulated dealer decisions
affect hypothetical sector customers under this project's own hand-specified
scenario assumptions (docs/README_honesty_paragraph.md). See the Phase 7
mastery checkpoint in the README for the full contrast.

WHAT THIS MODULE DOES
------------------------
Takes a completed `Simulation.run()` result dict (Phase 4 regime mode, so
`order_log` entries carry `sector` and `military_linked` tags) and computes,
per sector and cutting across military/civilian within each sector:
  - orders received, filled, rejected, and fill rate
  - gallium inventory coverage days (physical inventory / trailing average
    daily consumption)
  - shortage duration and frequency (consecutive-day runs of negative
    `available_kg`)
  - "emergency willingness-to-pay" (the average willingness-to-pay of orders
    that needed emergency-order escalation to fill, vs. everything else --
    a proxy for how much extra value those specific commitments represented)

WHY THIS IS PURE POST-PROCESSING, NOT A NEW SIMULATION MECHANISM
------------------------------------------------------------------------
Every field this module needs (sector, military_linked, fill_type,
willingness_to_pay, the inventory tranches over time) was already being
recorded by Phases 3-4 for other reasons. Phase 7's contribution is
SUMMARIZING that data into the specific metrics the roadmap asks for, not
generating new data -- this keeps src/simulation.py's own scope from
creeping every phase, and means Phase 7 can be re-run against any past
simulation result without re-simulating anything.

WHY COVERAGE DAYS USES A ROLLING WINDOW, NOT THE WHOLE-RUN AVERAGE
------------------------------------------------------------------------
"How many days of supply do we have left, at the CURRENT rate of
consumption" is only meaningful if "current" means recent, not a
full-simulation average that blends calm and severe periods together.
Register Section 14 uses a 30-day trailing window -- long enough to smooth
day-to-day noise, short enough to reflect a genuinely current
consumption rate.

WHY SHORTAGE EPISODES REUSE available_kg < 0 RATHER THAN A NEW THRESHOLD
------------------------------------------------------------------------------
`available_kg` (Phase 3) is already explicitly designed to be a meaningful
negative number -- "a real signal of overextension," per its own module
docstring. Defining "in shortage" as available_kg < 0 keeps this metric
consistent with every scarcity-reactive mechanism already built on that
same signal (the scarcity premium, Phase 5; the reorder-point logic, Phase
3) instead of introducing a second, potentially-inconsistent scarcity
definition.

LIMITATIONS (explicit, not hidden)
-----------------------------------
- Coverage days and shortage episodes are computed from the DEALER's
  aggregate inventory tranches, not per-sector inventory -- there is only
  one physical stockpile in this project (no per-sector warehousing), so
  "coverage days for the Solar sector" really means "coverage days for the
  whole dealer, viewed alongside Solar's own demand rate." This is stated
  explicitly wherever coverage days are reported per sector.
- "Emergency willingness-to-pay" is a proxy (the WTP of orders that
  happened to need emergency escalation), not a measurement of a real
  auction or elicited valuation.
- Everything in this module is scoped to the current Phase 3/4/5/6 supply
  chain and demand model's own limitations (already documented in their
  respective sections) -- this analysis layer does not fix or hide any of
  those; it just summarizes their downstream sector-level consequences.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
There would be no sector-level lens on this project's results at all --
Phase 4 already tracks pooled sector fill rates, but nothing about coverage
days, shortage duration/frequency, or the emergency-willingness-to-pay
proxy, all of which the roadmap explicitly asks Phase 7 to produce.
"""

from dataclasses import dataclass


@dataclass
class SectorStressTestParams:
    coverage_days_window: int = 30  # register Section 14


def compute_sector_fill_stats(order_log: list[dict]) -> dict:
    """
    Per sector: orders received/filled/rejected, fill rate, and a
    military-linked vs. civilian-linked breakdown WITHIN that sector --
    the roadmap's explicit ask to cut the military/civilian comparison
    "across all four sectors, not just within Defense & Aerospace."
    """
    sectors = sorted({o["sector"] for o in order_log})
    report = {}
    for sector in sectors:
        sector_orders = [o for o in order_log if o["sector"] == sector]
        n_orders = len(sector_orders)
        n_filled = sum(1 for o in sector_orders if o["filled"])

        mil_orders = [o for o in sector_orders if o["military_linked"]]
        civ_orders = [o for o in sector_orders if not o["military_linked"]]
        mil_filled = sum(1 for o in mil_orders if o["filled"])
        civ_filled = sum(1 for o in civ_orders if o["filled"])

        report[sector] = {
            "n_orders": n_orders,
            "n_filled": n_filled,
            "n_rejected": n_orders - n_filled,
            "fill_rate": (n_filled / n_orders) if n_orders else None,
            "military": {
                "n_orders": len(mil_orders),
                "n_filled": mil_filled,
                "fill_rate": (mil_filled / len(mil_orders)) if mil_orders else None,
            },
            "civilian": {
                "n_orders": len(civ_orders),
                "n_filled": civ_filled,
                "fill_rate": (civ_filled / len(civ_orders)) if civ_orders else None,
            },
        }
    return report


def compute_coverage_days(
    tranche_history: list[dict], order_log: list[dict], window_days: int = 30
) -> list[dict]:
    """
    Register Section 14: coverage_days[t] = physical_kg[t] / trailing
    average daily consumption over the last `window_days` days. Returns
    None for days with zero recent consumption (infinite coverage, not a
    number worth plotting as a large finite value).
    """
    kg_sold_by_day = {}
    for o in order_log:
        if o["filled"]:
            kg_sold_by_day[o["t"]] = kg_sold_by_day.get(o["t"], 0.0) + o["size_kg"]

    results = []
    for row in tranche_history:
        t = row["t"]
        window_start = max(0, t - window_days + 1)
        total_sold = sum(kg_sold_by_day.get(day, 0.0) for day in range(window_start, t + 1))
        avg_daily_consumption = total_sold / window_days
        coverage_days = (
            row["physical_kg"] / avg_daily_consumption if avg_daily_consumption > 1e-9 else None
        )
        results.append({"t": t, "coverage_days": coverage_days, "physical_kg": row["physical_kg"]})
    return results


def compute_shortage_episodes(tranche_history: list[dict]) -> list[dict]:
    """
    Consecutive-day runs where available_kg < 0 (register Section 14: reuses
    Section 3's own existing "available inventory can be meaningfully
    negative" definition, not a new threshold). Returns a list of
    {start_t, end_t, duration_days} for each distinct episode.
    """
    episodes = []
    in_episode = False
    start_t = None
    prev_t = None

    for row in tranche_history:
        t, available = row["t"], row["available_kg"]
        if available < 0:
            if not in_episode:
                in_episode = True
                start_t = t
        else:
            if in_episode:
                episodes.append({"start_t": start_t, "end_t": prev_t, "duration_days": prev_t - start_t + 1})
                in_episode = False
        prev_t = t

    if in_episode:
        episodes.append({"start_t": start_t, "end_t": prev_t, "duration_days": prev_t - start_t + 1})

    return episodes


def compute_emergency_wtp_stats(order_log: list[dict]) -> dict:
    """
    Register Section 14 / roadmap: "emergency willingness to pay" -- the
    average willingness-to-pay of orders that needed emergency-order
    escalation to fill (fill_type == "emergency_backordered"), contrasted
    with every other fill type, as a proxy for how much extra value those
    specific commitments represented.
    """
    emergency_wtps = [o["willingness_to_pay"] / o["price"] - 1.0 for o in order_log
                       if o["fill_type"] == "emergency_backordered"]
    other_wtps = [o["willingness_to_pay"] / o["price"] - 1.0 for o in order_log
                  if o["fill_type"] != "emergency_backordered"]
    return {
        "n_emergency_orders": len(emergency_wtps),
        "mean_emergency_wtp_premium": (
            sum(emergency_wtps) / len(emergency_wtps) if emergency_wtps else None
        ),
        "mean_other_wtp_premium": sum(other_wtps) / len(other_wtps) if other_wtps else None,
    }


def compute_sector_stress_report(result: dict, params: SectorStressTestParams = None) -> dict:
    """
    Combines every metric above into one report dict. `result` must be a
    Phase 4 regime-mode `Simulation.run()` output (needs `order_log` with
    `sector`/`military_linked` tags and `tranche_history`).
    """
    p = params or SectorStressTestParams()
    return {
        "sector_fill_stats": compute_sector_fill_stats(result["order_log"]),
        "coverage_days": compute_coverage_days(
            result["tranche_history"], result["order_log"], window_days=p.coverage_days_window
        ),
        "shortage_episodes": compute_shortage_episodes(result["tranche_history"]),
        "emergency_wtp_stats": compute_emergency_wtp_stats(result["order_log"]),
    }
