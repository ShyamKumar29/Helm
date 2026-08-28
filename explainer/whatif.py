# explainer/whatif.py — non-destructive what-if (FINAL.md §10): copies state in memory,
# applies overrides, calls engine.decide twice (baseline + scenario), returns the comparison.
# Never writes to the database — explainer has no DB access at all (router.py's HTTP
# self-calls are read-only GETs).
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from contracts.schemas import DecisionObject, State
from engine.decide import decide

# Frozen override shape — FINAL.md §10 "whatif override shape":
#   {"kind": "RECEIVABLE_DELAY", "target_id": "RCV-0004", "delay_days": 21}
#   {"kind": "RATE_CHANGE",      "target_id": "FAC-001",   "new_apr_pct": 18.0}
#   {"kind": "CASH_DELTA",       "target_id": null,        "amount": -500000.0}
#   {"kind": "NEW_OBLIGATION",   "target_id": null,        "amount": 900000.0, "due_date": "..."}


def _apply_one(state_dict: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    kind = override.get("kind")

    if kind == "RECEIVABLE_DELAY":
        for r in state_dict["receivables"]:
            if r["id"] == override.get("target_id"):
                d = date.fromisoformat(r["expected_date"]) + timedelta(days=int(override.get("delay_days", 0)))
                r["expected_date"] = d.isoformat()

    elif kind == "RATE_CHANGE":
        for f in state_dict["facilities"]:
            if f["id"] == override.get("target_id"):
                f["apr_pct"] = float(override.get("new_apr_pct", f["apr_pct"]))

    elif kind == "CASH_DELTA":
        state_dict["cash_available"] = round(float(state_dict["cash_available"]) + float(override.get("amount", 0.0)), 2)

    elif kind == "NEW_OBLIGATION":
        n = len(state_dict["obligations"]) + 1
        state_dict["obligations"].append(
            {
                "id": f"OBL-WHATIF-{n:03d}",
                "label": "What-if obligation",
                "category": "TAX",
                "amount": float(override.get("amount", 0.0)),
                "due_date": override.get("due_date"),
                "hard": True,
            }
        )
    # An unknown `kind` is silently a no-op rather than a 500 — the frozen set is exactly
    # these four (FINAL.md §10); a fifth one showing up is a contract change, not a crash.

    return state_dict


def apply_overrides(state: State, overrides: list[dict[str, Any]]) -> State:
    data = state.model_dump(mode="json")
    for override in overrides:
        data = _apply_one(data, override)
    return State.model_validate(data)


def run(state: State, overrides: list[dict[str, Any]], weights: dict | None) -> dict[str, Any]:
    baseline_decision: DecisionObject = decide(
        state, weights=weights, previous=None, trigger={"type": "MANUAL", "description": "what-if baseline"}
    )
    modified_state = apply_overrides(state, overrides)
    whatif_decision: DecisionObject = decide(
        modified_state,
        weights=weights,
        # by_alias=True matters here for the same reason api/services/engine_gateway.py's
        # validated_decision() docstring calls out: DiffFlip.from_ is aliased to the wire
        # name "from" ("from" is a Python keyword). Without it, decide()'s own diffing
        # against this `previous` dict reads a key that was never written.
        previous=baseline_decision.model_dump(mode="json", by_alias=True),
        trigger={"type": "WHATIF", "description": "what-if scenario"},
    )

    return {
        "baseline_decision": baseline_decision.model_dump(mode="json", by_alias=True),
        "whatif_decision": whatif_decision.model_dump(mode="json", by_alias=True),
        "diff": (
            whatif_decision.diff_from_previous.model_dump(mode="json", by_alias=True)
            if whatif_decision.diff_from_previous
            else None
        ),
    }
