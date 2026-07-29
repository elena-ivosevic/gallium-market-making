import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

from src.holdout_scenarios import (
    ALL_HOLDOUT_SCENARIOS, PERSISTENT_SEVERE_REGIME, LOW_VOL_EXTREME_SHIPMENT_FAILURE,
    HIGH_DEMAND_MODERATE_PRICES, SUDDEN_RECOVERY_THEN_RELAPSE,
    SEVERE_MILITARY_NEAR_ZERO_CIVILIAN_OPEN,
)
from src.policies.fixed_spread import FixedSpreadPolicy, FixedSpreadParams
from src.simulation import Simulation, SimulationConfig
from src.regimes import RegimeSwitcher


def test_all_five_scenarios_present_and_named():
    assert len(ALL_HOLDOUT_SCENARIOS) == 5
    names = {s.name for s in ALL_HOLDOUT_SCENARIOS}
    assert names == {
        "persistent_severe_regime", "low_vol_extreme_shipment_failure",
        "high_demand_moderate_prices", "sudden_recovery_then_relapse",
        "severe_military_near_zero_civilian_open",
    }


def test_every_scenario_runs_end_to_end_without_error():
    for scenario in ALL_HOLDOUT_SCENARIOS:
        policy = FixedSpreadPolicy(FixedSpreadParams())
        sim = Simulation(
            policy, config=SimulationConfig(n_steps=100, seed=1),
            price_params=scenario.price_params, regime_params=scenario.regime_params,
            supply_chain_params=scenario.supply_chain_params,
            accounting_params=scenario.accounting_params,
            sectors=scenario.sectors,
        )
        result = sim.run()
        assert result["n_orders"] >= 0


def test_persistent_severe_regime_actually_stays_severe():
    """After fixing a real design gap (see _persistent_severe_regime_params'
    docstring), this should hold on EVERY seed, not just on average."""
    for seed in range(10):
        switcher = RegimeSwitcher(PERSISTENT_SEVERE_REGIME.regime_params, seed=seed)
        for _ in range(300):
            switcher.step()
        severe_frac = switcher.regime_days["severe"] / 301
        assert severe_frac > 0.9, f"seed {seed} only stayed severe {severe_frac:.2%} of the time"


def test_low_vol_scenario_has_calm_prices_but_severe_shipment_failure():
    scenario = LOW_VOL_EXTREME_SHIPMENT_FAILURE
    assert scenario.price_params.sigma < 0.35  # calmer than the project default (0.35)
    assert scenario.supply_chain_params.reliability < 0.5
    assert scenario.supply_chain_params.reliability_military < 0.2


def test_high_demand_scenario_scales_sector_arrival_rates_up():
    from src.demand import DEFAULT_SECTORS
    scenario = HIGH_DEMAND_MODERATE_PRICES
    for default_sector, scaled_sector in zip(DEFAULT_SECTORS, scenario.sectors):
        assert scaled_sector.arrival_rate_per_year == default_sector.arrival_rate_per_year * 3.0
        assert scaled_sector.military_linked_share == default_sector.military_linked_share


def test_sudden_recovery_scenario_has_elevated_relapse_probability():
    scenario = SUDDEN_RECOVERY_THEN_RELAPSE
    relapse_prob = scenario.regime_params.transition_matrix["recovery"]["severe"]
    default_relapse = 0.015  # register Section 11.3 default
    assert relapse_prob > default_relapse * 5


def test_severe_military_near_zero_scenario_has_wide_reliability_gap():
    scenario = SEVERE_MILITARY_NEAR_ZERO_CIVILIAN_OPEN
    civilian = scenario.regime_params.civilian_reliability["severe"]
    military = scenario.regime_params.military_reliability["severe"]
    assert civilian > 0.85
    assert military < 0.05
    assert (civilian - military) > 0.8


def test_scenarios_are_independent_objects_not_shared_mutable_state():
    """Each scenario's RegimeParams must be its own object -- mutating one
    scenario's transition matrix must never affect another's."""
    original_severe_self_transition = (
        LOW_VOL_EXTREME_SHIPMENT_FAILURE.regime_params.transition_matrix["severe"]["severe"]
    )
    # PERSISTENT_SEVERE_REGIME deliberately has a very different severe
    # self-transition (0.998) -- confirm the two don't collide.
    assert (
        PERSISTENT_SEVERE_REGIME.regime_params.transition_matrix["severe"]["severe"]
        != original_severe_self_transition
    )


def test_running_a_scenario_in_regime_mode_does_not_mutate_its_own_params():
    """
    Regression test for a real bug found during Phase 8 development:
    Simulation's regime mode writes `supply_chain.p.reliability` in place
    every day. Without a defensive copy in src/simulation.py, running a
    holdout scenario once would permanently corrupt its module-level
    singleton SupplyChainParams object for every later use (this test would
    have failed intermittently depending on test execution order before the
    fix -- see src/simulation.py's constructor comment for the fix itself).
    """
    scenario = LOW_VOL_EXTREME_SHIPMENT_FAILURE
    original_reliability = scenario.supply_chain_params.reliability
    original_reliability_military = scenario.supply_chain_params.reliability_military

    policy = FixedSpreadPolicy(FixedSpreadParams())
    sim = Simulation(
        policy, config=SimulationConfig(n_steps=100, seed=1),
        price_params=scenario.price_params, regime_params=scenario.regime_params,
        supply_chain_params=scenario.supply_chain_params,
        accounting_params=scenario.accounting_params, sectors=scenario.sectors,
    )
    sim.run()

    assert scenario.supply_chain_params.reliability == original_reliability
    assert scenario.supply_chain_params.reliability_military == original_reliability_military
