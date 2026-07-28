"""
policies/dp_toy_example.py
============================

Phase 6 PREREQUISITE (per the roadmap: "Do not begin the full DP model
until you can solve this toy example comfortably"). A 3-inventory-state,
2-action, 2-period Bellman problem, solved BY HAND below, then confirmed
against a programmatic backward-induction solver -- if the two ever
disagree, the hand derivation (not the code) is wrong, and this module's
whole purpose is to catch that before any real DP policy gets built on
shakier ground.

THE PROBLEM
-----------
States: Low (0), Medium (1), High (2) -- inventory level.
Actions: Sell (aggressive/low price, more volume), Hold (defensive/high
         price, preserves inventory).
Horizon: T = 2 decision periods (t=0, t=1), terminal value at t=2.

Immediate reward R(state, action) -- Sell always earns more immediate
reward than Hold in the same state (it captures more volume), but Hold
preserves inventory for the future:

    R(Low,    Sell) = 8,   R(Low,    Hold) = 3
    R(Medium, Sell) = 10,  R(Medium, Hold) = 4
    R(High,   Sell) = 12,  R(High,   Hold) = 5

Transition probabilities P(next_state | state, action):

    Sell: Low -> Low (1.0)             [nothing left to sell further down]
          Medium -> Low (0.7), Medium -> Medium (0.3)
          High -> Medium (0.7), High -> High (0.3)
    Hold: Low -> Low (1.0)
          Medium -> Medium (0.9), Medium -> Low (0.1)
          High -> High (0.9), High -> Medium (0.1)

Terminal value V_2(state) -- ending inventory has value:

    V_2(Low) = 0,  V_2(Medium) = 5,  V_2(High) = 30

WHY V_2(High) = 30, NOT SOMETHING SMALLER
--------------------------------------------
This is the single most important design choice in the toy problem. With a
small terminal value, Sell would dominate in every state (higher immediate
reward, and the future barely matters) -- correctly solvable, but boring: a
purely greedy/myopic policy would already get it right, so the exercise
wouldn't demonstrate anything DP-specific. V_2(High)=30 is deliberately
large enough that, near the horizon, PRESERVING a High inventory position
(Hold) beats selling it down (Sell) -- exactly the "immediate profit vs.
future value of preserved inventory" tension Phase 6's own stated goal
describes. See the hand derivation below for the exact numbers where this
flips.

HAND DERIVATION (do this before running any code -- that's the point)
--------------------------------------------------------------------------
Bellman equation: V_t(s) = max_a [ R(s,a) + sum_s' P(s'|s,a) * V_{t+1}(s') ]

Step 1 -- V_1(s), using V_2 as the continuation value:

  V_1(Low):
    Sell: 8 + 1.0*V_2(Low)=0            = 8
    Hold: 3 + 1.0*V_2(Low)=0            = 3
    -> max = 8 (Sell)

  V_1(Medium):
    Sell: 10 + 0.7*V_2(Low)=0 + 0.3*V_2(Medium)=5*0.3=1.5   = 11.5
    Hold: 4 + 0.9*V_2(Medium)=5*0.9=4.5 + 0.1*V_2(Low)=0    = 8.5
    -> max = 11.5 (Sell)

  V_1(High):
    Sell: 12 + 0.7*V_2(Medium)=5*0.7=3.5 + 0.3*V_2(High)=30*0.3=9   = 24.5
    Hold: 5 + 0.9*V_2(High)=30*0.9=27 + 0.1*V_2(Medium)=5*0.1=0.5   = 32.5
    -> max = 32.5 (HOLD -- the flip happens here)

  V_1 = [8, 11.5, 32.5], optimal actions at t=1: [Sell, Sell, Hold]

Step 2 -- V_0(s), using V_1 as the continuation value:

  V_0(Low):
    Sell: 8 + 1.0*V_1(Low)=8             = 16
    Hold: 3 + 1.0*V_1(Low)=8             = 11
    -> max = 16 (Sell)

  V_0(Medium):
    Sell: 10 + 0.7*V_1(Low)=8*0.7=5.6 + 0.3*V_1(Medium)=11.5*0.3=3.45   = 19.05
    Hold: 4 + 0.9*V_1(Medium)=11.5*0.9=10.35 + 0.1*V_1(Low)=8*0.1=0.8  = 15.15
    -> max = 19.05 (Sell)

  V_0(High):
    Sell: 12 + 0.7*V_1(Medium)=11.5*0.7=8.05 + 0.3*V_1(High)=32.5*0.3=9.75  = 29.8
    Hold: 5 + 0.9*V_1(High)=32.5*0.9=29.25 + 0.1*V_1(Medium)=11.5*0.1=1.15 = 35.4
    -> max = 35.4 (HOLD again)

  V_0 = [16, 19.05, 35.4], optimal actions at t=0: [Sell, Sell, Hold]

THE LESSON, STATED PLAINLY
------------------------------
At High inventory, Hold is optimal at BOTH decision points, even though
Sell earns strictly more immediate reward (12 vs. 5) in that exact state,
every single time. A myopic policy that only looked at immediate reward
would get Low and Medium right by coincidence (Sell happens to be optimal
there too) but would get High wrong -- it would sell down valuable
inventory right before the terminal payoff rewards holding onto it. This
is the entire reason dynamic programming exists: VALUE, not immediate
reward, is what a rational policy should maximize, and value requires
looking forward.

WHAT BREAKS IF THIS MODULE IS REMOVED
--------------------------------------
Nothing downstream depends on it programmatically -- it exists purely as
the roadmap's required comprehension checkpoint before building the real
DP policy (src/policies/dynamic_programming.py). Removing it doesn't break
any simulation, but it removes the verified evidence that the hand
derivation above is actually correct, which the real DP policy's backward
induction logic is a direct, larger-scale generalization of.
"""

import numpy as np

STATES = ("low", "medium", "high")
ACTIONS = ("sell", "hold")

REWARD = {
    ("low", "sell"): 8.0, ("low", "hold"): 3.0,
    ("medium", "sell"): 10.0, ("medium", "hold"): 4.0,
    ("high", "sell"): 12.0, ("high", "hold"): 5.0,
}

TRANSITIONS = {
    ("low", "sell"): {"low": 1.0},
    ("low", "hold"): {"low": 1.0},
    ("medium", "sell"): {"low": 0.7, "medium": 0.3},
    ("medium", "hold"): {"medium": 0.9, "low": 0.1},
    ("high", "sell"): {"medium": 0.7, "high": 0.3},
    ("high", "hold"): {"high": 0.9, "medium": 0.1},
}

TERMINAL_VALUE = {"low": 0.0, "medium": 5.0, "high": 30.0}

# The hand-derived values above, kept as literals so tests can confirm the
# programmatic solver matches them exactly -- not just "some" answer.
HAND_DERIVED_V1 = {"low": 8.0, "medium": 11.5, "high": 32.5}
HAND_DERIVED_V1_ACTIONS = {"low": "sell", "medium": "sell", "high": "hold"}
HAND_DERIVED_V0 = {"low": 16.0, "medium": 19.05, "high": 35.4}
HAND_DERIVED_V0_ACTIONS = {"low": "sell", "medium": "sell", "high": "hold"}


def solve_toy_problem() -> dict:
    """
    Programmatic backward-induction solver for the toy problem above.
    Returns {"V": [V_0_dict, V_1_dict, V_2_dict], "policy": [pi_0_dict, pi_1_dict]}
    -- generic backward induction over T=2 periods, not hard-coded to the
    specific numbers, so it's a genuine independent check on the hand
    derivation rather than the same arithmetic copy-pasted twice.
    """
    T = 2
    V = [None] * (T + 1)
    policy = [None] * T
    V[T] = dict(TERMINAL_VALUE)

    for t in range(T - 1, -1, -1):
        V[t] = {}
        policy[t] = {}
        for s in STATES:
            best_value = -np.inf
            best_action = None
            for a in ACTIONS:
                continuation = sum(
                    prob * V[t + 1][s_next] for s_next, prob in TRANSITIONS[(s, a)].items()
                )
                value = REWARD[(s, a)] + continuation
                if value > best_value:
                    best_value = value
                    best_action = a
            V[t][s] = best_value
            policy[t][s] = best_action

    return {"V": V, "policy": policy}
