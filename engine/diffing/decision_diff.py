# engine/diffing/decision_diff.py — FINAL.md §12 build order step "H+16-H+19 — diffs and
# polish": "compares the new decision to `previous` and fills `diff_from_previous`. Assign
# `reason_code` on each flip by checking which constraint became newly binding. This is what
# makes the live shock demo readable." The reason attached to a flip is simply the winning
# action's own `primary_reason_code` — it already *is* "which constraint became newly
# binding" for whatever the agent now prefers.
from __future__ import annotations

from typing import Any

from engine.actions.candidates import Candidate


def compute(previous: dict[str, Any] | None, chosen: dict[str, Candidate]) -> dict[str, Any]:
    if previous is None:
        return {
            "previous_decision_id": None,
            "flipped": [],
            "added": [{"target_id": tid} for tid in chosen],
            "removed": [],
        }

    prev_action_by_target = {a["target_id"]: a["action"] for a in previous.get("actions", [])}

    flipped: list[dict[str, str]] = []
    for target_id, candidate in chosen.items():
        prev_action = prev_action_by_target.get(target_id)
        if prev_action is not None and prev_action != candidate.action:
            flipped.append(
                {
                    "target_id": target_id,
                    "from": prev_action,
                    "to": candidate.action,
                    "reason_code": candidate.primary_reason_code,
                }
            )

    added = [{"target_id": tid} for tid in chosen if tid not in prev_action_by_target]
    removed = [{"target_id": tid} for tid in prev_action_by_target if tid not in chosen]

    return {
        "previous_decision_id": previous.get("decision_id"),
        "flipped": flipped,
        "added": added,
        "removed": removed,
    }
