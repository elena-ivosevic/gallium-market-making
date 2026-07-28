import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.regimes import RegimeSwitcher, RegimeParams, REGIMES


def test_starts_in_configured_initial_regime():
    switcher = RegimeSwitcher(RegimeParams(initial_regime="normal"), seed=1)
    assert switcher.current_regime == "normal"
    assert switcher.history == ["normal"]


def test_invalid_initial_regime_rejected():
    with pytest.raises(ValueError):
        RegimeSwitcher(RegimeParams(initial_regime="chaos"), seed=1)


def test_transition_matrix_rows_sum_to_one():
    params = RegimeParams()
    for regime in REGIMES:
        row_sum = sum(params.transition_matrix[regime].values())
        assert row_sum == pytest.approx(1.0, abs=1e-9)


def test_incomplete_transition_matrix_rejected():
    params = RegimeParams()
    del params.transition_matrix["severe"]
    with pytest.raises(ValueError):
        RegimeSwitcher(params, seed=1)


def test_normal_regime_is_highly_persistent():
    """Register Section 11.3: Normal has ~333-day expected duration --
    across a 500-day run starting in Normal, most days should stay Normal."""
    switcher = RegimeSwitcher(RegimeParams(initial_regime="normal"), seed=2)
    for _ in range(500):
        switcher.step()
    normal_frac = switcher.regime_days["normal"] / 501
    assert normal_frac > 0.5


def test_severe_only_reachable_via_delayed():
    """Register Section 11.3: Normal can never transition directly to Severe."""
    params = RegimeParams()
    assert params.transition_matrix["normal"]["severe"] == 0.0


def test_recovery_can_relapse_into_severe():
    """Register Section 11.3: Recovery is explicitly conditional/revocable."""
    params = RegimeParams()
    assert params.transition_matrix["recovery"]["severe"] > 0.0


def test_regimes_persist_across_multiple_consecutive_days():
    """A regime with high self-transition probability should show runs of
    multiple consecutive identical days, not flicker every day."""
    switcher = RegimeSwitcher(RegimeParams(initial_regime="normal"), seed=3)
    for _ in range(300):
        switcher.step()
    # Count the longest run of consecutive identical regimes
    longest_run = 1
    current_run = 1
    for i in range(1, len(switcher.history)):
        if switcher.history[i] == switcher.history[i - 1]:
            current_run += 1
            longest_run = max(longest_run, current_run)
        else:
            current_run = 1
    assert longest_run > 10  # far more than a coin-flip process would produce


def test_lookups_return_regime_specific_values():
    switcher = RegimeSwitcher(RegimeParams(initial_regime="severe"), seed=4)
    assert switcher.jump_intensity_multiplier() == 6.0
    assert switcher.civilian_reliability() == 0.40
    assert switcher.military_reliability() == 0.15
    assert switcher.hawkes_excitation() == 0.60


def test_military_reliability_always_below_civilian_in_every_regime():
    """Register Section 11.2: the military channel should be less reliable
    than civilian in every regime, not just Normal."""
    params = RegimeParams()
    for regime in REGIMES:
        assert params.military_reliability[regime] < params.civilian_reliability[regime]


def test_severe_and_recovery_both_show_wider_reliability_gaps_than_normal():
    """
    Register Section 11.2's actual, self-consistent story (corrected after
    this test first caught an inconsistency between the register's prose and
    its own numbers): the civilian-military reliability gap should be WIDE
    in Severe (military end-use ban persists during acute disruption) AND in
    Recovery (civilian licensing eases faster than military restrictions,
    per phase0_research_notes.md Section 2 -- so a recovering civilian
    channel temporarily WIDENS the gap versus a lagging military channel,
    it doesn't narrow it). Normal and Delayed, with no disruption or only
    early friction, should show the narrowest gaps.
    """
    params = RegimeParams()
    gaps = {r: params.civilian_reliability[r] - params.military_reliability[r] for r in REGIMES}
    assert gaps["severe"] > gaps["normal"]
    assert gaps["recovery"] > gaps["normal"]


def test_step_is_deterministic_given_a_seed():
    s1 = RegimeSwitcher(RegimeParams(), seed=42)
    s2 = RegimeSwitcher(RegimeParams(), seed=42)
    for _ in range(100):
        s1.step()
        s2.step()
    assert s1.history == s2.history
