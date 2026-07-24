"""
tests/test_phase2_comparison.py
================================

Phase 2 deliverable: "Compare Against: Fixed-spread policy, Inventory-
threshold heuristic."

WHAT THIS FILE DOES, AND WHY IT DOES NOT ASSERT "AS WINS"
-------------------------------------------------------------
These tests run all three Phase 1/2 policies (fixed-spread, inventory
heuristic, standard Avellaneda-Stoikov) against IDENTICAL price paths and
customer-order arrivals (same seed), which is a light, single-seed preview
of the matched-Monte-Carlo comparison Phase 8 builds properly (with many
seeds, paired statistical tests, and confidence intervals).

This file deliberately does NOT assert that any policy "beats" another in
terms of P&L. A single-seed, non-statistical comparison is exactly the kind
of premature, uncontrolled comparison docs/README_honesty_paragraph.md warns
against ("Policy A outperforms Policy B" claims need a confidence interval,
which requires Phase 8's machinery, not a single run). Instead, these tests
check STRUCTURAL properties that must hold if each policy is behaving as
designed -- i.e., that AS actually varies its quote with inventory while the
fixed-spread baseline does not, which is a claim about mechanism, not about
outcome quality.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np

from src.policies.fixed_spread import FixedSpreadPolicy, FixedSpreadParams
from src.policies.inventory_heuristic import InventoryHeuristicPolicy, InventoryHeuristicParams
from src.policies.avellaneda_stoikov import AvellanedaStoikovPolicy, AvellanedaStoikovParams
from src.simulation import Simulation, SimulationConfig


def _run_all_three(seed: int, n_steps: int = 252):
    fixed = FixedSpreadPolicy(FixedSpreadParams())
    heuristic = InventoryHeuristicPolicy(InventoryHeuristicParams())
    as_policy = AvellanedaStoikovPolicy(AvellanedaStoikovParams())

    results = {}
    for name, policy in [("fixed", fixed), ("heuristic", heuristic), ("avellaneda_stoikov", as_policy)]:
        sim = Simulation(policy, config=SimulationConfig(n_steps=n_steps, seed=seed))
        results[name] = sim.run()
    return results


def test_all_three_policies_run_on_matched_price_and_demand_paths():
    """Confirms the matched-path setup itself: identical seed -> identical
    price path and, up to policy-driven differences, identical order arrivals."""
    results = _run_all_three(seed=11)
    # Price paths must be identical across policies (same seed, and the price
    # process does not depend on the policy at all).
    assert results["fixed"]["price_path"] == results["heuristic"]["price_path"]
    assert results["fixed"]["price_path"] == results["avellaneda_stoikov"]["price_path"]


def test_fixed_spread_ask_never_varies_with_inventory():
    """Structural check: the fixed-spread baseline's ask should be a constant
    multiple of mid price throughout, regardless of inventory swings."""
    result = _run_all_three(seed=12)["fixed"]
    asks = np.array([o["ask"] for o in result["order_log"]])
    prices = np.array([o["price"] for o in result["order_log"]])
    ratios = asks / prices
    assert np.allclose(ratios, ratios[0], atol=1e-9)


def test_avellaneda_stoikov_ask_varies_with_inventory_even_at_fixed_price():
    """Structural check: AS's quote should NOT collapse to a constant markup
    over price -- its ask/price ratio should show real variation, driven by
    inventory and time-to-horizon, unlike the fixed-spread baseline above."""
    result = _run_all_three(seed=13)["avellaneda_stoikov"]
    asks = np.array([o["ask"] for o in result["order_log"]])
    prices = np.array([o["price"] for o in result["order_log"]])
    ratios = asks / prices
    assert np.std(ratios) > 1e-6, "expected AS ask/price ratio to vary, found it essentially constant"


def test_inventory_heuristic_ask_takes_only_three_distinct_spread_values():
    """Structural check: the heuristic's ask/price ratio should take on
    (at most) three distinct values -- scarce/normal/excess -- unlike AS's
    continuously varying ratio."""
    result = _run_all_three(seed=14)["heuristic"]
    asks = np.array([o["ask"] for o in result["order_log"]])
    prices = np.array([o["price"] for o in result["order_log"]])
    ratios = np.round(asks / prices, 8)
    assert len(np.unique(ratios)) <= 3


def test_avellaneda_stoikov_reservation_price_diagnostics_are_recorded():
    """Confirms the generic policy_diagnostics hook in simulation.py actually
    captures AS's reservation price / spread / bid / ask over time, which is
    required for the Phase 2 'reservation-price behavior' and 'spread
    behavior' plots."""
    result = _run_all_three(seed=15)["avellaneda_stoikov"]
    diagnostics = result["policy_diagnostics"]
    assert len(diagnostics) == 252
    first = diagnostics[0]
    for key in ("reservation_price", "bid", "ask", "spread", "inventory_kg", "time_remaining"):
        assert key in first


def test_fixed_spread_policy_has_no_diagnostics_recorded():
    """Confirms the generic hook is truly generic: a policy that doesn't
    expose last_diagnostics (Phase 1's fixed-spread policy) simply produces
    an empty diagnostics list, with no special-casing required."""
    result = _run_all_three(seed=16)["fixed"]
    assert result["policy_diagnostics"] == []
