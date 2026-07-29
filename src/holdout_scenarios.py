"""
holdout_scenarios.py
=====================

Phase 8 deliverable: Holdout Scenarios. Five named, concretely parameterized
scenario combinations, reserved specifically to check whether findings from
earlier phases hold outside the conditions they were originally observed
under -- none of these combinations were used to calibrate any default
parameter elsewhere in this project.

WHY THESE FIVE, AND WHY THEY COUNT AS GENUINE HOLDOUTS
------------------------------------------------------------
Every default parameter elsewhere in this project (regime transition
probabilities, reliability figures, sector definitions) was chosen via
qualitative research and judgment calls (Sections 1-14), never by fitting
or optimizing against any specific scenario. These five combinations are
DELIBERATELY more extreme than any default -- persistent Severe regimes,
decoupled price/supply-chain stress, demand-driven (not price-driven)
scarcity, a scripted-feeling regime relapse, and the register's own
most-extreme military/civilian reliability gap -- so that a finding which
only holds near the defaults (e.g., Phase 5/7's "the priority overlay's
effect is small") can be explicitly re-checked somewhere it might not.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Every finding in this project would remain checked only near its own
default calibration -- there would be no explicit, reserved set of more
extreme conditions to confirm (or overturn) those findings against.
"""

from dataclasses import dataclass, field

from src.price_process import PriceProcessParams
from src.regimes import RegimeParams
from src.supply_chain import SupplyChainParams
from src.accounting import AccountingParams
from src.demand import SectorParams, DEFAULT_SECTORS


@dataclass
class HoldoutScenario:
    name: str
    description: str
    price_params: PriceProcessParams
    regime_params: RegimeParams
    supply_chain_params: SupplyChainParams
    accounting_params: AccountingParams
    sectors: list = field(default_factory=lambda: None)


def _persistent_severe_regime_params() -> RegimeParams:
    """
    Severe is not just self-sticky (0.998) -- every OTHER state is also
    biased heavily back toward Severe. An earlier version of this function
    only modified Severe's own row, leaving Recovery/Delayed/Normal at their
    default (low) probability of returning to Severe -- which meant that if
    the chain ever left Severe even briefly (a low-probability event, but
    one that becomes likely over a long enough window), it would almost
    never come back, producing enormous seed-to-seed variance (some seeds
    near 100% Severe, others under 5%) rather than genuine persistence. That
    was caught by `test_persistent_severe_regime_actually_stays_severe`
    failing on a single seed, then confirmed as a systematic issue by
    checking many seeds (mean ~78% but a huge spread) -- fixed here by
    making every state's return path to Severe strong, not just Severe's
    own self-transition.
    """
    p = RegimeParams(initial_regime="severe")
    p.transition_matrix = {
        "normal": {"normal": 0.5, "delayed": 0.5, "severe": 0.0, "recovery": 0.0},
        "delayed": {"normal": 0.0, "delayed": 0.5, "severe": 0.5, "recovery": 0.0},
        "severe": {"normal": 0.0, "delayed": 0.0, "severe": 0.998, "recovery": 0.002},
        "recovery": {"normal": 0.0, "delayed": 0.0, "severe": 0.5, "recovery": 0.5},
    }
    return p


def _sudden_recovery_then_relapse_params() -> RegimeParams:
    p = RegimeParams(initial_regime="severe")
    p.transition_matrix = {
        "normal": p.transition_matrix["normal"],
        "delayed": p.transition_matrix["delayed"],
        "severe": {"normal": 0.0, "delayed": 0.0, "severe": 0.90, "recovery": 0.10},
        "recovery": {"normal": 0.02, "delayed": 0.0, "severe": 0.15, "recovery": 0.83},
    }
    return p


def _severe_military_near_zero_params() -> RegimeParams:
    p = RegimeParams(initial_regime="severe")
    p.civilian_reliability = dict(p.civilian_reliability)
    p.military_reliability = dict(p.military_reliability)
    p.civilian_reliability["severe"] = 0.90
    p.military_reliability["severe"] = 0.02
    return p


PERSISTENT_SEVERE_REGIME = HoldoutScenario(
    name="persistent_severe_regime",
    description=(
        "Sustained disruption far longer than the register's own ~67-day expected "
        "Severe duration (Section 11.3) -- Severe self-transition raised to 0.998, "
        "an expected ~500-day duration."
    ),
    price_params=PriceProcessParams(),
    regime_params=_persistent_severe_regime_params(),
    supply_chain_params=SupplyChainParams(),
    accounting_params=AccountingParams(safety_stock_kg=60.0),
)

LOW_VOL_EXTREME_SHIPMENT_FAILURE = HoldoutScenario(
    name="low_vol_extreme_shipment_failure",
    description=(
        "Calm prices (low sigma, low jump intensity) decoupled from severe supply "
        "failure (very low civilian AND military reliability) -- tests whether "
        "policies over-rely on price signals while the real risk is physical."
    ),
    price_params=PriceProcessParams(sigma=0.10, jump_intensity=0.5),
    regime_params=RegimeParams(),
    supply_chain_params=SupplyChainParams(reliability=0.15, reliability_military=0.05),
    accounting_params=AccountingParams(safety_stock_kg=60.0),
)

HIGH_DEMAND_MODERATE_PRICES = HoldoutScenario(
    name="high_demand_moderate_prices",
    description=(
        "Sector arrival rates scaled 3x with otherwise Normal-regime, unremarkable "
        "prices -- tests physical scarcity arising from sheer VOLUME, decoupled "
        "from price-driven panic."
    ),
    price_params=PriceProcessParams(),
    regime_params=RegimeParams(),
    supply_chain_params=SupplyChainParams(),
    accounting_params=AccountingParams(safety_stock_kg=60.0),
    sectors=[
        SectorParams(s.name, s.arrival_rate_per_year * 3.0, s.order_size_mean_kg,
                     s.wtp_spread_frac, s.military_linked_share, s.order_size_sigma)
        for s in DEFAULT_SECTORS
    ],
)

SUDDEN_RECOVERY_THEN_RELAPSE = HoldoutScenario(
    name="sudden_recovery_then_relapse",
    description=(
        "Severe regime that transitions to Recovery relatively quickly, but with "
        "a 10x-elevated Recovery-to-Severe relapse probability (0.15 vs. the "
        "register's 0.015 default) -- tests whether policies 'relax' prematurely "
        "after an apparent recovery."
    ),
    price_params=PriceProcessParams(),
    regime_params=_sudden_recovery_then_relapse_params(),
    supply_chain_params=SupplyChainParams(),
    accounting_params=AccountingParams(safety_stock_kg=60.0),
)

SEVERE_MILITARY_NEAR_ZERO_CIVILIAN_OPEN = HoldoutScenario(
    name="severe_military_near_zero_civilian_open",
    description=(
        "The register's own most extreme documented case (Sections 2 and 10): a "
        "military end-use ban that persists even while general civilian licensing "
        "stays largely open -- civilian reliability 90%, military reliability 2%."
    ),
    price_params=PriceProcessParams(),
    regime_params=_severe_military_near_zero_params(),
    supply_chain_params=SupplyChainParams(reliability=0.90, reliability_military=0.02),
    accounting_params=AccountingParams(safety_stock_kg=60.0),
)

ALL_HOLDOUT_SCENARIOS = [
    PERSISTENT_SEVERE_REGIME,
    LOW_VOL_EXTREME_SHIPMENT_FAILURE,
    HIGH_DEMAND_MODERATE_PRICES,
    SUDDEN_RECOVERY_THEN_RELAPSE,
    SEVERE_MILITARY_NEAR_ZERO_CIVILIAN_OPEN,
]
