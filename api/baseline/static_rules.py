# api/baseline/static_rules.py — B7. The baseline agent, FINAL.md section 11.8 verbatim
# (docs/backend/10-PHASE-B7-baseline-and-metrics.md section 3). Deliberately simple and
# deliberately plausible: fixed cash reserve, no forecasting, no uncertainty, no
# re-optimisation, no supplier awareness. Do not improve it — its entire value is that it is
# what a real finance team actually does, and beating an improved version proves nothing.
#
# Emits the same `DecisionObject` shape the engine emits (FINAL.md section 8.4: "Both agents
# emit the same shape so the frontend can render either"), so it validates against the exact
# same Pydantic model and executes through the exact same api/services/executor.py path.
#
# The baseline does not score. `score_breakdown` and every `rejected_alternatives[].net_value`
# stay 0.0 rather than fabricate a number the rule never computed (see the phase doc: "the
# kind of thing a finance-literate judge catches") — the one honest exception is
# `discount_captured`, which is a mechanical fact of the rule firing, not a scored judgement.
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from api.enums import POLICY_BASELINE
from api.models import Decision, Facility, Invoice
from api.services import clock, ids, ledger

RESERVE = Decimal(
    500000
)  # fixed ₹5,00,000 cash reserve, no forecasting (FINAL.md 11.8)

ZERO_WEIGHTS = {
    "discount": 0.0,
    "financing_cost": 0.0,
    "penalty": 0.0,
    "liquidity_risk": 0.0,
    "supplier_stress": 0.0,
}

ZERO_BREAKDOWN = {
    "discount_captured": 0.0,
    "penalty_incurred": 0.0,
    "financing_cost": 0.0,
    "liquidity_risk_cost": 0.0,
    "supplier_stress_delta": 0.0,
    "net_value": 0.0,
}


def _open_invoices(session: Session) -> list[Invoice]:
    return (
        session.query(Invoice)
        .filter(
            Invoice.policy == POLICY_BASELINE, Invoice.status.in_(("OPEN", "SCHEDULED"))
        )
        .order_by(Invoice.id)
        .all()
    )


def _bank_facility_id(session: Session) -> str | None:
    row = (
        session.query(Facility)
        .filter(Facility.policy == POLICY_BASELINE, Facility.type == "BANK_LINE")
        .first()
    )
    return row.id if row is not None else None


def _previous_decision(session: Session) -> dict | None:
    row = (
        session.query(Decision)
        .filter(Decision.policy == POLICY_BASELINE)
        .order_by(Decision.sim_day.desc(), Decision.created_at.desc())
        .first()
    )
    return dict(row.payload) if row is not None else None


def _action(
    n: int,
    inv: Invoice,
    action_type: str,
    amount: float,
    execute_on: str | None,
    funding_source: str,
    facility_id: str | None,
    primary_reason_code: str,
    rejected_action: str,
    rejected_reason_code: str,
    discount_captured: float = 0.0,
) -> dict:
    breakdown = dict(ZERO_BREAKDOWN)
    breakdown["discount_captured"] = round(discount_captured, 2)
    return {
        "action_id": ids.action_id(n),
        "target_type": "INVOICE",
        "target_id": inv.id,
        "supplier_id": inv.supplier_id,
        "action": action_type,
        "amount": round(amount, 2),
        "execute_on": execute_on,
        "funding_source": funding_source,
        "facility_id": facility_id,
        "confidence": 1.0,  # deterministic rule, no uncertainty modelled (FINAL.md 11.8)
        "score_breakdown": breakdown,
        "binding_constraints": [],
        "primary_reason_code": primary_reason_code,
        "rejected_alternatives": [
            {
                "action": rejected_action,
                "net_value": 0.0,  # never fabricated — the baseline does not score
                "delta": 0.0,
                "reason_code": rejected_reason_code,
            }
        ],
        "status": "PROPOSED",
    }


def run(session: Session, sim) -> dict:
    """One BASELINE `DecisionObject` for `sim.as_of`. Returns a dict without
    `decision_id`/`run_at`/`sim_day`/`policy` stamped — the caller (sim_loop step 7) fills
    those in immediately before validation, the same pattern step 6 uses for the AGENT
    (docs/backend/07-PHASE-B4-state-builder-and-engine.md step 3: simulation facts the
    engine/agent cannot know about itself)."""
    invoices = _open_invoices(session)
    cash = float(ledger.latest_balance(session, POLICY_BASELINE))
    reserve = float(RESERVE)
    tomorrow = clock.add_days(sim.as_of, 1).isoformat()
    bank_facility_id = _bank_facility_id(session)

    previous = _previous_decision(session)
    prev_action_by_target = {
        a["target_id"]: a["action"] for a in (previous or {}).get("actions", [])
    }

    actions: list[dict] = []
    for n, inv in enumerate(invoices, start=1):
        amount = float(inv.amount)
        discount_pct = float(inv.discount_pct) if inv.discount_pct is not None else 0.0

        if inv.discount_until == sim.as_of and cash > amount:
            net_amount = round(amount * (1 - discount_pct / 100.0), 2)
            discount_amt = round(amount - net_amount, 2)
            actions.append(
                _action(
                    n,
                    inv,
                    "PAY_EARLY_DISCOUNT",
                    net_amount,
                    tomorrow,
                    "CASH",
                    None,
                    "DISCOUNT_CAPTURED",
                    "PAY_AT_MATURITY",
                    "NO_BETTER_ALTERNATIVE",
                    discount_captured=discount_amt,
                )
            )
        elif inv.due_date == sim.as_of:
            if cash - reserve >= amount:
                actions.append(
                    _action(
                        n,
                        inv,
                        "PAY_AT_MATURITY",
                        amount,
                        tomorrow,
                        "CASH",
                        None,
                        "PENALTY_AVOIDED",
                        "FINANCE_BANK",
                        "NO_BETTER_ALTERNATIVE",
                    )
                )
            else:
                actions.append(
                    _action(
                        n,
                        inv,
                        "FINANCE_BANK",
                        amount,
                        tomorrow,
                        "BANK_LINE",
                        bank_facility_id,
                        "INSUFFICIENT_CASH",
                        "PAY_AT_MATURITY",
                        "INSUFFICIENT_CASH",
                    )
                )
        else:
            actions.append(
                _action(
                    n,
                    inv,
                    "HOLD",
                    amount,
                    None,
                    "CASH",
                    None,
                    "NO_BETTER_ALTERNATIVE",
                    "PAY_NOW",
                    "NO_BETTER_ALTERNATIVE",
                )
            )

    deployable_cash = max(0.0, cash - reserve)  # the baseline's naive idea of a floor
    buffer_required = max(0.0, cash - deployable_cash)

    flipped = []
    for a in actions:
        prev_action = prev_action_by_target.get(a["target_id"])
        if prev_action is not None and prev_action != a["action"]:
            flipped.append(
                {
                    "target_id": a["target_id"],
                    "from": prev_action,
                    "to": a["action"],
                    "reason_code": a["primary_reason_code"],
                }
            )

    return {
        "trigger": {
            "type": "SCHEDULED",
            "event_id": None,
            "materiality_score": None,
            "description": "baseline daily rule run",
        },
        "cash_before": round(cash, 2),
        "buffer_required": round(buffer_required, 2),
        "deployable_cash": round(deployable_cash, 2),
        "objective_weights": ZERO_WEIGHTS,
        "objective_value": 0.0,
        "actions": actions,
        "facility_actions": [],
        "solver": {
            "method": "GREEDY_FALLBACK",
            "status": "FEASIBLE",
            "solve_ms": 0,
            "n_scenarios": 0,
            "fallback_used": False,
        },
        "diff_from_previous": {
            "previous_decision_id": (previous or {}).get("decision_id"),
            "flipped": flipped,
            "added": [],
            "removed": [],
        },
        "explanation": None,
    }
