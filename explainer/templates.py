# explainer/templates.py — the REQUIRED explainer (FINAL.md §17 scope cuts: this is cut
# #1's floor, "ship templates.py only" must always work, no API key, no network).
#
# CLAUDE.md rule 4: "The LLM never computes a number... the explainer only narrates a
# decision that already exists, using figures handed to it in the DecisionObject." This
# module takes that literally — every rupee figure in `narrative` is an f-string substitution
# of a field already on `decision`, and `grounded_fields` lists exactly which ones, so the
# "did it invent a number" check is trivially true here.
from __future__ import annotations

from typing import Any

ACTION_TEXT: dict[str, str] = {
    "PAY_NOW": "paying now from cash",
    "PAY_EARLY_DISCOUNT": "paying early to capture the discount",
    "PAY_AT_MATURITY": "paying at maturity",
    "DELAY": "delaying payment",
    "FINANCE_BANK": "financing via the bank line",
    "FINANCE_SUPPLIER": "financing via the supplier program",
    "HOLD": "holding",
}

REASON_TEXT: dict[str, str] = {
    "BUFFER_BREACH": "paying would have breached the liquidity floor",
    "DISCOUNT_CAPTURED": "the early-payment discount was worth capturing",
    "DISCOUNT_FORGONE": "the discount was forgone to preserve liquidity",
    "PENALTY_AVOIDED": "paying on time avoided the late penalty",
    "PENALTY_ACCEPTED": "the penalty was cheaper than the alternative",
    "FACILITY_LIMIT": "facility headroom was the binding constraint",
    "OBLIGATION_PRIORITY": "cash was reserved for an upcoming hard obligation",
    "SUPPLIER_CRITICAL": "the supplier's strategic importance forced earlier payment",
    "SUPPLIER_DISTRESS": "the supplier's liquidity stress forced earlier payment",
    "CHEAPER_FINANCING": "borrowing was cheaper than forgoing the discount",
    "INSUFFICIENT_CASH": "there wasn't enough cash on hand",
    "NO_BETTER_ALTERNATIVE": "no better alternative existed",
}


def _inr(v: float) -> str:
    return f"₹{v:,.0f}"


def _top_actions(decision: dict[str, Any], n: int = 3) -> list[tuple[int, dict[str, Any]]]:
    indexed = list(enumerate(decision.get("actions", [])))
    non_hold = [(i, a) for i, a in indexed if a.get("action") != "HOLD"]
    non_hold.sort(key=lambda ia: abs(ia[1].get("score_breakdown", {}).get("net_value", 0.0)), reverse=True)
    return non_hold[:n]


def build_explanation(decision: dict[str, Any]) -> dict[str, Any]:
    cash_before = decision.get("cash_before", 0.0)
    buffer_required = decision.get("buffer_required", 0.0)
    deployable_cash = decision.get("deployable_cash", 0.0)
    trigger = decision.get("trigger") or {}
    trigger_desc = trigger.get("description")

    top = _top_actions(decision)
    grounded_fields = ["cash_before", "buffer_required", "deployable_cash"]

    if not top:
        headline = "Holding course — no action needed today"
    elif len(top) == 1:
        _, a = top[0]
        headline = f"{ACTION_TEXT.get(a['action'], a['action']).capitalize()} on {a['target_id']}"
    else:
        headline = f"Re-optimized {len(top)} invoice(s), largest first: {top[0][1]['target_id']}"

    narrative_parts = [
        f"Today's deployable cash is {_inr(deployable_cash)} against {_inr(cash_before)} on hand, "
        f"keeping {_inr(buffer_required)} in reserve for what's still committed."
    ]
    if trigger_desc:
        narrative_parts.append(trigger_desc + ".")

    for i, a in top:
        sb = a.get("score_breakdown", {})
        grounded_fields.append(f"actions[{i}].amount")
        grounded_fields.append(f"actions[{i}].score_breakdown")
        reason = REASON_TEXT.get(a.get("primary_reason_code", ""), "")
        sentence = (
            f"{a['target_id']}: {_inr(a.get('amount', 0.0))}, "
            f"{ACTION_TEXT.get(a['action'], a['action'])} — {reason}, "
            f"net {_inr(sb.get('net_value', 0.0))}."
        )
        narrative_parts.append(sentence)

    flipped = (decision.get("diff_from_previous") or {}).get("flipped") or []
    if flipped:
        grounded_fields.append("diff_from_previous.flipped")
        names = ", ".join(f"{f['target_id']} ({f['from']} → {f['to']})" for f in flipped[:4])
        narrative_parts.append(f"Changed from the previous cycle: {names}.")

    tradeoffs = []
    for i, a in top:
        sb = a.get("score_breakdown", {})
        cost = sb.get("financing_cost", 0.0) + sb.get("penalty_incurred", 0.0) + sb.get("liquidity_risk_cost", 0.0)
        tradeoffs.append(
            f"{a['target_id']}: {_inr(sb.get('discount_captured', 0.0))} discount against "
            f"{_inr(cost)} of financing/penalty/liquidity cost, net {_inr(sb.get('net_value', 0.0))}."
        )
    if not tradeoffs:
        tradeoffs.append("No invoice needed a paid/held trade-off this cycle.")

    would_change_if = []
    for _i, a in top[:2]:
        alts = a.get("rejected_alternatives") or []
        if alts:
            alt = alts[0]
            would_change_if.append(
                f"If {REASON_TEXT.get(alt.get('reason_code', ''), 'the constraint above')} stopped holding, "
                f"{a['target_id']} would move to {ACTION_TEXT.get(alt['action'], alt['action'])}."
            )
    would_change_if.append(
        f"If deployable cash falls below {_inr(deployable_cash)}, today's plan gets re-solved."
    )
    grounded_fields.append("deployable_cash")

    key_assumptions = [
        "Figures come from this cycle's own Monte Carlo forecast and optimizer run — nothing here is re-derived.",
        f"{_inr(deployable_cash)} deployable cash is treated as the hard ceiling for today's discretionary spend.",
    ]
    if trigger_desc:
        key_assumptions.append(trigger_desc)

    return {
        "decision_id": decision.get("decision_id", ""),
        "headline": headline,
        "narrative": " ".join(narrative_parts),
        "key_assumptions": key_assumptions,
        "tradeoffs": tradeoffs,
        "would_change_if": would_change_if,
        "generated_by": "template",
        "grounded_fields": sorted(set(grounded_fields)),
    }
