import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np
import pytest

from src.ablation import build_ablation_variants, run_ablation_study
from src.evaluation import confidence_interval


def test_all_nine_variants_present():
    variants = build_ablation_variants()
    expected = {
        "full_model", "no_hawkes", "no_regime_switching", "no_shipment_risk_premium",
        "no_replacement_cost_premium", "no_commitment_premium", "no_scarcity_premium",
        "no_priority_overlay", "standard_AS",
    }
    assert set(variants.keys()) == expected


def test_ablation_study_runs_end_to_end():
    result = run_ablation_study(seeds=[1, 2, 3], n_steps=60)
    assert set(result["metrics"].keys()) == set(build_ablation_variants().keys())
    for name, metrics_list in result["metrics"].items():
        assert len(metrics_list) == 3


def test_ablation_study_uses_matched_seeds_across_variants():
    """Every variant must see the identical price path for a given seed --
    the matched-Monte-Carlo guarantee (src/evaluation.py) applies here too."""
    result = run_ablation_study(seeds=[5], n_steps=60)
    price_paths = [r[0]["price_path"] for r in result["raw_results"].values()]
    assert all(p == price_paths[0] for p in price_paths)


def test_standard_as_variant_uses_plain_avellaneda_stoikov():
    from src.policies.avellaneda_stoikov import AvellanedaStoikovPolicy
    factory, _ = build_ablation_variants()["standard_AS"]
    policy = factory()
    assert isinstance(policy, AvellanedaStoikovPolicy)
    assert not hasattr(policy, "p") or not hasattr(policy.p, "scarcity_gamma")


def test_no_hawkes_variant_zeroes_excitation_in_every_regime():
    from src.ablation import _no_hawkes_regime_params
    p = _no_hawkes_regime_params()
    assert all(v == 0.0 for v in p.hawkes_excitation.values())


def test_no_regime_switching_variant_stays_at_normal():
    from src.ablation import _no_switching_regime_params
    from src.regimes import RegimeSwitcher

    p = _no_switching_regime_params()
    switcher = RegimeSwitcher(p, seed=1)
    for _ in range(200):
        switcher.step()
    assert switcher.regime_days["normal"] == 201  # never left Normal, ever


def test_no_priority_overlay_variant_sets_p_to_zero():
    _, kwargs = build_ablation_variants()["no_priority_overlay"]
    assert kwargs["priority_overlay_params"].p == 0.0


def test_full_model_variant_sets_p_to_one():
    _, kwargs = build_ablation_variants()["full_model"]
    assert kwargs["priority_overlay_params"].p == 1.0


def test_each_premium_ablation_zeroes_exactly_one_gamma():
    from src.policies.scarcity_adjusted_as import ScarcityAdjustedASParams

    default = ScarcityAdjustedASParams()
    checks = {
        "no_shipment_risk_premium": "shipment_risk_gamma",
        "no_replacement_cost_premium": "replacement_cost_pass_through",
        "no_commitment_premium": "commitment_gamma",
        "no_scarcity_premium": "scarcity_gamma",
    }
    variants = build_ablation_variants()
    for variant_name, field_name in checks.items():
        factory, _ = variants[variant_name]
        policy = factory()
        assert getattr(policy.p, field_name) == 0.0
        # And confirm every OTHER premium field is untouched (still default)
        for other_field in checks.values():
            if other_field != field_name:
                assert getattr(policy.p, other_field) == getattr(default, other_field)


def test_ablation_variants_are_independent_objects_not_shared_mutable_state():
    """Each call to build_ablation_variants() must construct fresh
    RegimeParams/PriorityOverlayParams objects -- guards against the exact
    mutation bug found and fixed in Phase 8 (src/simulation.py deep-copies
    supply_chain_params, but regime_params/priority_overlay_params objects
    passed here must also not be accidentally shared across variants)."""
    variants = build_ablation_variants()
    full_model_regime = variants["full_model"][1]["regime_params"]
    no_hawkes_regime = variants["no_hawkes"][1]["regime_params"]
    assert full_model_regime is not no_hawkes_regime
    assert full_model_regime.hawkes_excitation != no_hawkes_regime.hawkes_excitation
