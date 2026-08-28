# api/services/executor.py — B5. Applies a persisted decision's due actions to the world:
# ledger rows, invoice/facility state transitions. The only place a scheduled action turns
# into cash movement (docs/backend/08-PHASE-B5-sim-loop.md section 3 step 4). Escalates
# rather than silently skipping when cash is short — an invoice must never just vanish off
# the books.
from __future__ import annotations

import logging

from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from api.models import Decision, Event, Facility, Invoice
from api.services import ledger
from api.services.serializers import event_out

log = logging.getLogger(__name__)


def emit_event(session: Session, sim, type_: str, payload: dict) -> dict:
    """Persist and shape one SIM-sourced event. `sim` is the sim_loop.DayContext for the
    day in progress — duck-typed here (not imported) so this module and sim_loop never
    import each other (00-BACKEND-OVERVIEW.md section 3: services stay one-directional)."""
    row = Event(
        event_id=sim.next_event_id(),
        sim_day=sim.sim_day,
        date=sim.as_of,
        type=type_,
        source="SIM",
        payload=payload,
        materiality_score=None,
        triggered_reoptimization=False,
        triggered_decision_id=None,
    )
    session.add(row)
    session.flush()
    return event_out(row)


def _newest_decision(session: Session, policy: str) -> Decision | None:
    return (
        session.query(Decision)
        .filter(Decision.policy == policy)
        .order_by(Decision.sim_day.desc(), Decision.created_at.desc())
        .first()
    )


def _penalty(invoice: Invoice, days_late: int) -> float:
    # FINAL.md section 11.3 — never exceeds invoice.max_delay_days.
    days_late = min(days_late, invoice.max_delay_days)
    bps = float(invoice.penalty_bps_per_day)
    return round(float(invoice.amount) * (bps / 10000.0) * days_late, 2)


def execute_scheduled_actions(session: Session, sim, policy: str) -> list[dict]:
    """Execute every PROPOSED action in `policy`'s newest decision whose `execute_on` is
    today. Mutates only `action["status"]` on the stored payload — never any other engine
    output field (docs/backend/07-PHASE-B4 step 3 / engine_gateway.py docstring)."""
    decision = _newest_decision(session, policy)
    if decision is None:
        return []

    payload = decision.payload
    today = sim.as_of.isoformat()
    events: list[dict] = []
    touched = False

    for action in payload.get("actions", []):
        if action.get("execute_on") != today or action.get("status") != "PROPOSED":
            continue
        if action.get("target_type") != "INVOICE":
            continue

        invoice = session.get(Invoice, (action["target_id"], policy))
        if invoice is None:
            log.warning(
                "policy=%s action %s targets missing invoice %s",
                policy,
                action.get("action_id"),
                action.get("target_id"),
            )
            continue

        outcome = _apply(session, sim, policy, invoice, action)
        touched = True
        if outcome is not None:
            events.append(outcome)

    if touched:
        flag_modified(decision, "payload")
        session.flush()

    return events


def _apply(
    session: Session, sim, policy: str, invoice: Invoice, action: dict
) -> dict | None:
    kind = action["action"]
    amount = float(action["amount"])

    if kind == "HOLD":
        action["status"] = "EXECUTED"
        return None

    if kind in ("PAY_NOW", "PAY_AT_MATURITY"):
        return _pay_cash(
            session, sim, policy, invoice, action, amount, penalty=0.0, discount=0.0
        )

    if kind == "PAY_EARLY_DISCOUNT":
        discount_pct = invoice.discount_pct or 0.0
        discount_amt = round(amount * (discount_pct / 100.0), 2)
        return _pay_cash(
            session,
            sim,
            policy,
            invoice,
            action,
            amount - discount_amt,
            penalty=0.0,
            discount=discount_amt,
        )

    if kind == "DELAY":
        days_late = max(0, (sim.as_of - invoice.due_date).days)
        penalty = _penalty(invoice, days_late)
        return _pay_cash(
            session, sim, policy, invoice, action, amount, penalty=penalty, discount=0.0
        )

    if kind == "FINANCE_BANK":
        return _finance_bank(session, sim, policy, invoice, action, amount)

    if kind == "FINANCE_SUPPLIER":
        return _finance_supplier(session, sim, policy, invoice, action, amount)

    log.warning(
        "unknown action kind %r on %s, leaving PROPOSED", kind, action.get("action_id")
    )
    return None


def _pay_cash(
    session, sim, policy, invoice, action, cash_amount, *, penalty, discount
) -> dict | None:
    required = cash_amount + penalty
    if float(ledger.latest_balance(session, policy)) < required:
        action["status"] = "ESCALATED"
        log.warning(
            "policy=%s invoice=%s escalated: cash short for required %.2f",
            policy,
            invoice.id,
            required,
        )
        return None

    ledger.post(
        session,
        policy,
        sim.sim_day,
        sim.as_of,
        -cash_amount,
        "INVOICE_PAYMENT",
        invoice.id,
    )
    if penalty > 0:
        ledger.post(
            session, policy, sim.sim_day, sim.as_of, -penalty, "PENALTY", invoice.id
        )

    invoice.status = "PAID"
    invoice.paid_on = sim.as_of
    invoice.paid_amount = cash_amount + penalty
    invoice.funding_source = "CASH"
    action["status"] = "EXECUTED"

    return emit_event(
        session,
        sim,
        "INVOICE_PAID",
        {
            "invoice_id": invoice.id,
            "amount": round(cash_amount + penalty, 2),
            "funding_source": "CASH",
            "discount_captured": discount,
            "penalty_paid": penalty,
        },
    )


def _finance_bank(session, sim, policy, invoice, action, amount) -> dict:
    facility_id = action.get("facility_id")
    facility = session.get(Facility, (facility_id, policy)) if facility_id else None
    if facility is not None:
        facility.drawn = float(facility.drawn) + amount

    # Two ledger rows, never one, for a financed payment (section 4) — draw in, payment out.
    ledger.post(
        session, policy, sim.sim_day, sim.as_of, amount, "FACILITY_DRAW", facility_id
    )
    ledger.post(
        session, policy, sim.sim_day, sim.as_of, -amount, "INVOICE_PAYMENT", invoice.id
    )

    invoice.status = "FINANCED"
    invoice.paid_on = sim.as_of
    invoice.paid_amount = amount
    invoice.funding_source = "BANK_LINE"
    action["status"] = "EXECUTED"

    return emit_event(
        session,
        sim,
        "INVOICE_PAID",
        {
            "invoice_id": invoice.id,
            "amount": round(amount, 2),
            "funding_source": "BANK_LINE",
            "discount_captured": 0.0,
            "penalty_paid": 0.0,
        },
    )


def _finance_supplier(session, sim, policy, invoice, action, amount) -> dict:
    facility_id = action.get("facility_id")
    facility = session.get(Facility, (facility_id, policy)) if facility_id else None
    if facility is not None:
        facility.drawn = float(facility.drawn) + amount

    # No cash movement today — the financier pays the supplier; we settle at maturity.
    invoice.status = "FINANCED"
    invoice.paid_on = sim.as_of
    invoice.paid_amount = amount
    invoice.funding_source = "SUPPLIER_FINANCE"
    action["status"] = "EXECUTED"

    return emit_event(
        session,
        sim,
        "INVOICE_PAID",
        {
            "invoice_id": invoice.id,
            "amount": round(amount, 2),
            "funding_source": "SUPPLIER_FINANCE",
            "discount_captured": 0.0,
            "penalty_paid": 0.0,
        },
    )
