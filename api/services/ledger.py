# api/services/ledger.py — B5. The only writer of cash_ledger. Append-only: no UPDATE, no
# in-place balance mutation, ever (CLAUDE.md rule B3 / docs/backend/08-PHASE-B5-sim-loop.md
# section 4). Current cash for a policy is the `balance` of its newest row — never summed or
# recomputed elsewhere.
#
# Reasons are a small closed vocabulary so `SELECT reason, sum(delta) FROM cash_ledger WHERE
# policy=... GROUP BY reason` always answers "where did the money go" in one query:
#   OPENING_BALANCE, RECEIVABLE_COLLECTED, OBLIGATION, INVOICE_PAYMENT, FACILITY_DRAW,
#   FACILITY_REPAY, INTEREST, PENALTY
from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from api.models import CashLedger


def latest_balance(session: Session, policy: str) -> Decimal:
    row = (
        session.query(CashLedger)
        .filter(CashLedger.policy == policy)
        .order_by(CashLedger.sim_day.desc(), CashLedger.id.desc())
        .first()
    )
    return row.balance if row is not None else Decimal(0)


def post(
    session: Session,
    policy: str,
    sim_day: int,
    date_: date,
    delta: float,
    reason: str,
    ref_id: str | None,
) -> Decimal:
    """Append one ledger row and return the new balance. Every rupee that moves goes through
    here — there is no other way to change cash."""
    delta_d = Decimal(str(round(float(delta), 2)))
    prev = latest_balance(session, policy)
    row = CashLedger(
        sim_day=sim_day,
        date=date_,
        policy=policy,
        delta=delta_d,
        balance=prev + delta_d,
        reason=reason,
        ref_id=ref_id,
    )
    session.add(row)
    # autoflush is off (api/db.py) — flush so a second post() call for the same policy later
    # in the same day (e.g. a financed payment's two rows) sees this row's balance as `prev`.
    session.flush()
    return row.balance
