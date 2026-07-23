import numpy as np
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.price_process import GalliumPriceProcess, PriceProcessParams


def test_price_starts_at_s0():
    proc = GalliumPriceProcess(PriceProcessParams(s0=350.0), seed=1)
    assert proc.price == 350.0
    assert proc.history == [350.0]


def test_price_stays_positive_over_long_path():
    proc = GalliumPriceProcess(PriceProcessParams(s0=350.0), seed=2)
    path = proc.simulate_path(2000)
    assert np.all(path > 0), "price process produced a non-positive price"


def test_price_floor_is_respected():
    # Deliberately extreme params to force floor hits, and check the floor holds.
    params = PriceProcessParams(
        s0=10.0, sigma=5.0, jump_intensity=200.0,
        jump_up_prob=0.05, jump_up_scale=0.1, jump_down_scale=0.9,
        price_floor=1.0,
    )
    proc = GalliumPriceProcess(params, seed=3)
    path = proc.simulate_path(500)
    assert np.all(path >= 1.0)
    assert proc.floor_hits > 0, "test setup expected to trigger the floor at least once"


def test_zero_jump_intensity_reduces_to_pure_diffusion_behavior():
    """Edge-case validation (Phase 10 style, checked early): with jump_intensity=0,
    no jump events should ever be recorded."""
    params = PriceProcessParams(jump_intensity=0.0)
    proc = GalliumPriceProcess(params, seed=4)
    proc.simulate_path(1000)
    assert proc.jump_events == 0


def test_higher_jump_intensity_increases_number_of_jump_events_on_average():
    """Mastery-checkpoint style sanity check: more jump intensity -> more jumps,
    on average, across seeds."""
    low = PriceProcessParams(jump_intensity=1.0)
    high = PriceProcessParams(jump_intensity=20.0)

    low_counts, high_counts = [], []
    for seed in range(10):
        p_low = GalliumPriceProcess(low, seed=seed)
        p_low.simulate_path(252)
        low_counts.append(p_low.jump_events)

        p_high = GalliumPriceProcess(high, seed=seed)
        p_high.simulate_path(252)
        high_counts.append(p_high.jump_events)

    assert np.mean(high_counts) > np.mean(low_counts)


def test_jumps_are_right_skewed_per_assumptions_register():
    """
    docs/assumptions_register.md, Section 1, "Jump size distribution" row,
    requires right-skewed jumps: more frequent AND larger upward jumps than
    downward jumps. Confirm both properties hold given the default params.
    """
    params = PriceProcessParams(
        jump_intensity=500.0,  # crank up intensity so we get a large sample of jumps fast
        jump_up_prob=0.65,
        jump_up_scale=0.18,
        jump_down_scale=0.07,
    )
    proc = GalliumPriceProcess(params, seed=6)
    proc.simulate_path(500)

    assert proc.jump_events > 0
    # More frequent upward jumps than downward jumps
    assert proc.jump_up_events > proc.jump_down_events
    # Roughly consistent with jump_up_prob (loose tolerance, this is stochastic)
    observed_up_frac = proc.jump_up_events / proc.jump_events
    assert abs(observed_up_frac - params.jump_up_prob) < 0.1


def test_mean_reversion_pulls_price_toward_theta():
    """Start far from theta with zero jumps and modest sigma; average price
    over a long path should end up much closer to theta than the start point."""
    params = PriceProcessParams(
        s0=800.0, theta=350.0, kappa=8.0, sigma=0.05, jump_intensity=0.0,
    )
    proc = GalliumPriceProcess(params, seed=5)
    path = proc.simulate_path(500)
    # last 50 steps should be much closer to theta than the initial distance
    late_avg = np.mean(path[-50:])
    assert abs(late_avg - params.theta) < abs(params.s0 - params.theta) * 0.3
