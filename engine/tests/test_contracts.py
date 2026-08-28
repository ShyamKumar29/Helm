# engine/tests/test_contracts.py — FINAL.md §12 "Rules for you": "Keep tests/test_contracts.py
# running: for each fixture, assert decide() output validates against DecisionObject."
#
# Run: python -m pytest engine/tests/ -q  (from the repo root, so `engine`/`contracts` import)
from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.schemas import DecisionObject, Forecast, State
from engine.decide import decide, forecast

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"


def _load_state() -> State:
    return State.model_validate(json.loads((FIXTURES / "state.sample.json").read_text()))


def test_forecast_shape_and_invariants():
    state = _load_state()
    fc = forecast(state, horizon_days=90, n_paths=200)  # fewer paths — this just checks shape
    Forecast.model_validate(fc.model_dump(mode="json"))

    assert len(fc.buckets) == 91  # horizon_days + 1, FINAL.md §8.3
    assert fc.buckets[0].day_offset == 0
    assert fc.buckets[-1].day_offset == 90
    assert fc.deployable_cash >= 0
    assert fc.buffer_required == pytest.approx(max(0.0, state.cash_available - fc.deployable_cash), abs=0.01)


def test_decide_validates_and_covers_every_open_invoice():
    state = _load_state()
    decision = decide(state, weights=None, previous=None, trigger=None)
    DecisionObject.model_validate(decision.model_dump(mode="json"))

    covered = {a.target_id for a in decision.actions}
    assert covered == {inv.id for inv in state.invoices}  # FINAL.md §8.4: HOLD is explicit, never absent

    for action in decision.actions:
        assert len(action.rejected_alternatives) >= 1  # PS requirement 7
        for alt in action.rejected_alternatives:
            assert alt.delta <= 0
        if action.funding_source == "CASH":
            assert action.facility_id is None  # FINAL.md §8.4 rule


def test_decide_is_deterministic_for_the_same_state():
    state = _load_state()
    a = decide(state, weights=None, previous=None, trigger=None)
    b = decide(state, weights=None, previous=None, trigger=None)
    # decision_id/run_at/sim_day/policy are simulation facts a real caller overwrites — every
    # figure the engine itself produced must be identical (CLAUDE.md rule 6).
    assert a.deployable_cash == b.deployable_cash
    assert a.buffer_required == b.buffer_required
    assert [act.action for act in a.actions] == [act.action for act in b.actions]
    assert [act.amount for act in a.actions] == [act.amount for act in b.actions]


def test_diff_from_previous_flips_when_weights_change_direction():
    state = _load_state()
    first = decide(state, weights=None, previous=None, trigger=None)
    # Push liquidity risk aversion far higher — should not crash, still validates, and diffing
    # against `first` should never error even with zero flips.
    extreme_weights = {
        "discount": 1.0,
        "financing_cost": 1.0,
        "penalty": 1.0,
        "liquidity_risk": 5.0,
        "supplier_stress": 0.8,
    }
    second = decide(state, weights=extreme_weights, previous=first.model_dump(mode="json"), trigger=None)
    DecisionObject.model_validate(second.model_dump(mode="json"))
    assert second.diff_from_previous is not None
    assert second.diff_from_previous.previous_decision_id == first.decision_id

    # Regression: DiffFlip.from_ is aliased to the wire name "from" (contracts/schemas.py —
    # "from" is a Python keyword). A dump without by_alias=True silently produces "from_"
    # instead, which is exactly the bug explainer/whatif.py had before it started passing
    # by_alias=True consistently. Assert the wire shape directly rather than trusting a caller
    # to remember the flag.
    wire = second.model_dump(mode="json", by_alias=True)
    for flip in wire["diff_from_previous"]["flipped"]:
        assert "from" in flip and "from_" not in flip
