import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.demand import (
    SectorHawkesOrderFlow, SectorParams, MilitaryElasticityParams, HawkesParams,
    DEFAULT_SECTORS,
)


def test_default_sectors_produce_roughly_expected_proportions():
    flow = SectorHawkesOrderFlow(seed=1)
    all_orders = []
    for _ in range(500):
        all_orders.extend(flow.generate_orders(350.0, dt=1/252, demand_intensity_multiplier=1.0,
                                                  hawkes_excitation_strength=0.05))
    counts = {}
    for o in all_orders:
        counts[o.sector] = counts.get(o.sector, 0) + 1
    total = len(all_orders)
    # Semiconductors (140/275) should be the largest sector by a wide margin
    assert counts["semiconductors"] / total > counts["defense_aerospace"] / total


def test_every_order_is_tagged_with_a_known_sector():
    flow = SectorHawkesOrderFlow(seed=2)
    orders = []
    for _ in range(500):
        orders.extend(flow.generate_orders(350.0, dt=1/252, demand_intensity_multiplier=1.0,
                                             hawkes_excitation_strength=0.05))
    known_sectors = {s.name for s in DEFAULT_SECTORS}
    assert all(o.sector in known_sectors for o in orders)


def test_higher_demand_intensity_multiplier_increases_order_count():
    flow_low = SectorHawkesOrderFlow(seed=3)
    flow_high = SectorHawkesOrderFlow(seed=3)
    low_count = sum(
        len(flow_low.generate_orders(350.0, 1/252, demand_intensity_multiplier=1.0,
                                       hawkes_excitation_strength=0.0))
        for _ in range(252)
    )
    high_count = sum(
        len(flow_high.generate_orders(350.0, 1/252, demand_intensity_multiplier=2.5,
                                        hawkes_excitation_strength=0.0))
        for _ in range(252)
    )
    assert high_count > low_count


def test_hawkes_excitation_increases_clustering_of_order_arrivals():
    """With excitation strength 0, arrivals are plain Poisson (no clustering
    beyond chance). With high excitation, order counts should show more
    day-to-day variance (bursts followed by quiet periods) for the same
    average rate."""
    no_excitation = HawkesParams(decay_rate_per_year=8.0)
    flow_none = SectorHawkesOrderFlow(hawkes_params=no_excitation, seed=5)
    counts_none = [
        len(flow_none.generate_orders(350.0, 1/252, 1.0, hawkes_excitation_strength=0.0))
        for _ in range(500)
    ]

    flow_clustered = SectorHawkesOrderFlow(hawkes_params=no_excitation, seed=5)
    counts_clustered = [
        len(flow_clustered.generate_orders(350.0, 1/252, 1.0, hawkes_excitation_strength=2.0))
        for _ in range(500)
    ]

    assert np.var(counts_clustered) > np.var(counts_none)


def test_excitation_decays_over_time_when_no_new_orders_reinforce_it():
    flow = SectorHawkesOrderFlow(seed=6)
    flow.excitation = 10.0
    initial = flow.excitation
    # Run several days; excitation should trend down even though new orders
    # will add some back -- check it doesn't stay pinned at the initial spike.
    for _ in range(60):
        flow.generate_orders(350.0, 1/252, demand_intensity_multiplier=1.0,
                              hawkes_excitation_strength=0.05)
    assert flow.excitation < initial


def test_military_linked_orders_have_wider_wtp_spread_than_civilian():
    elasticity = MilitaryElasticityParams(wtp_spread_multiplier=2.5, wtp_mean_shift_frac=0.03)
    sectors = [SectorParams("test_sector", arrival_rate_per_year=5000.0, order_size_mean_kg=20.0,
                              wtp_spread_frac=0.05, military_linked_share=0.5)]
    flow = SectorHawkesOrderFlow(sectors=sectors, military_elasticity=elasticity, seed=7)
    orders = flow.generate_orders(350.0, dt=1.0, demand_intensity_multiplier=1.0,
                                    hawkes_excitation_strength=0.0)
    mil_wtp = [o.willingness_to_pay / 350.0 - 1 for o in orders if o.military_linked]
    civ_wtp = [o.willingness_to_pay / 350.0 - 1 for o in orders if not o.military_linked]
    assert len(mil_wtp) > 50 and len(civ_wtp) > 50  # enough samples
    assert np.std(mil_wtp) > np.std(civ_wtp)


def test_military_linked_orders_have_higher_mean_wtp():
    elasticity = MilitaryElasticityParams(wtp_spread_multiplier=2.5, wtp_mean_shift_frac=0.03)
    sectors = [SectorParams("test_sector", arrival_rate_per_year=5000.0, order_size_mean_kg=20.0,
                              wtp_spread_frac=0.05, military_linked_share=0.5)]
    flow = SectorHawkesOrderFlow(sectors=sectors, military_elasticity=elasticity, seed=8)
    orders = flow.generate_orders(350.0, dt=1.0, demand_intensity_multiplier=1.0,
                                    hawkes_excitation_strength=0.0)
    mil_wtp = np.mean([o.willingness_to_pay for o in orders if o.military_linked])
    civ_wtp = np.mean([o.willingness_to_pay for o in orders if not o.military_linked])
    assert mil_wtp > civ_wtp


def test_zero_elasticity_difference_makes_military_and_civilian_wtp_converge():
    """Mastery-checkpoint edge case (register Section 11.6): if the
    elasticity multiplier is 1.0 and mean shift is 0, tagging an order
    military-linked should have NO effect on its WTP distribution."""
    elasticity = MilitaryElasticityParams(wtp_spread_multiplier=1.0, wtp_mean_shift_frac=0.0)
    sectors = [SectorParams("test_sector", arrival_rate_per_year=5000.0, order_size_mean_kg=20.0,
                              wtp_spread_frac=0.05, military_linked_share=0.5)]
    flow = SectorHawkesOrderFlow(sectors=sectors, military_elasticity=elasticity, seed=9)
    orders = flow.generate_orders(350.0, dt=1.0, demand_intensity_multiplier=1.0,
                                    hawkes_excitation_strength=0.0)
    mil_wtp = [o.willingness_to_pay / 350.0 - 1 for o in orders if o.military_linked]
    civ_wtp = [o.willingness_to_pay / 350.0 - 1 for o in orders if not o.military_linked]
    assert np.mean(mil_wtp) == pytest.approx(np.mean(civ_wtp), abs=0.01)
    assert np.std(mil_wtp) == pytest.approx(np.std(civ_wtp), rel=0.15)
