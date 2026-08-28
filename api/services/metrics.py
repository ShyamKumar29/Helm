# api/services/metrics.py — B7. ComparisonMetrics: computed per policy from the ledger and
# the invoice table, never from decisions (a proposed decision is not an outcome). FINAL.md
# section 8.7 / docs/backend/10-PHASE-B7-baseline-and-metrics.md section 4.
#
# `discounts_captured` is reconstructed from `invoices`, not from INVOICE_PAID events, even
# though the B7 phase doc's table says "events". The frozen `Event` contract (FINAL.md
# section 8.6) has no `policy` column, so once AGENT and BASELINE hold identical invoice ids
# an INVOICE_PAID event cannot be attributed to a policy at all — see this module's
# `_discounts_captured` docstring. Flagged in the B7 handoff report as a contract/phase-doc
# conflict, not silently patched.
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from api.enums import POLICY_AGENT, POLICY_BASELINE
from api.models import CashLedger, Decision, Invoice, Obligation, Supplier
from contracts.schemas import ComparisonMetrics

# --------------------------------------------------------------------------------------
# pure math — no session, no DB, unit-testable on its own (FINAL.md section 8.7 / B7 doc §4)
# --------------------------------------------------------------------------------------


def net_working_capital_cost(
    financing_cost: float, penalties_paid: float, discounts_captured: float
) -> float:
    return round(financing_cost + penalties_paid - discounts_captured, 2)


def savings_per_day(nwc_cost: float, sim_day: int) -> float:
    return round(-nwc_cost / max(sim_day, 1), 2)


def health_score(
    *,
    shortfall_days: int,
    obligations_missed: int,
    penalties_paid: float,
    discounts_captured: float,
    avg_supplier_stress: float,
    financing_cost: float,
    sim_day: int,
    total_obligations: int,
    total_payable_value: float,
    total_discount_available: float,
) -> int:
    """FINAL.md section 8.7 / B7 doc section 4, verbatim. `max(sim_day, 1)` is the one-line
    fix for the day-0 divide-by-zero the doc calls out; `total_*` are world constants and
    must never be a moving window (see `_world_constants` below for why recomputing them per
    call is still safe here)."""
    v = (
        100
        - 30 * (shortfall_days / max(sim_day, 1))
        - 20 * (obligations_missed / max(total_obligations, 1))
        - 15 * (penalties_paid / max(1, total_payable_value)) * 100
        - 15 * (1 - discounts_captured / max(1, total_discount_available))
        - 10 * avg_supplier_stress
        - 10 * (financing_cost / max(1, total_payable_value)) * 100
    )
    return round(max(0.0, min(100.0, v)))


def compute_delta(agent: dict, baseline: dict) -> dict:
    """`delta` is always `agent - baseline` (FINAL.md section 8.7 fixture: 82 - 41 = 41)."""
    return {
        "net_working_capital_cost": round(
            agent["net_working_capital_cost"] - baseline["net_working_capital_cost"], 2
        ),
        "shortfall_days": agent["shortfall_days"] - baseline["shortfall_days"],
        "obligations_missed": agent["obligations_missed"]
        - baseline["obligations_missed"],
        "health_score": agent["health_score"] - baseline["health_score"],
    }


# --------------------------------------------------------------------------------------
# DB-backed per-policy aggregation
# --------------------------------------------------------------------------------------


def _world_constants(session: Session, policy: str) -> tuple[int, float, float]:
    """Computed on demand from `invoices`/`obligations`, not cached on `sim_state`.

    api/seed/seed.py already decided against adding columns there (B1's schema is frozen;
    see that module's `seed_world()` docstring/return value) — this follows the same
    precedent rather than reopening it for B7. Safe to recompute on every call: invoice
    `amount`/`discount_pct` never change after seeding, only `status` does, and this query
    is unfiltered by status, so the result is identical on sim_day 1 and sim_day 90 — no
    per-tick drift, which is the thing the phase doc is actually warning about.
    """
    total_obligations = session.query(Obligation).count()
    rows = (
        session.query(Invoice.amount, Invoice.discount_pct)
        .filter(Invoice.policy == policy)
        .all()
    )
    total_payable_value = sum(float(amount) for amount, _ in rows)
    total_discount_available = sum(
        float(amount) * float(disc_pct) / 100.0
        for amount, disc_pct in rows
        if disc_pct is not None
    )
    return (
        total_obligations,
        round(total_payable_value, 2),
        round(total_discount_available, 2),
    )


def _financing_cost(session: Session, policy: str) -> float:
    rows = (
        session.query(CashLedger.delta)
        .filter(CashLedger.policy == policy, CashLedger.reason == "INTEREST")
        .all()
    )
    return round(sum(-float(d) for (d,) in rows), 2)


def _penalties_paid(session: Session, policy: str) -> float:
    rows = (
        session.query(CashLedger.delta)
        .filter(CashLedger.policy == policy, CashLedger.reason == "PENALTY")
        .all()
    )
    return round(sum(-float(d) for (d,) in rows), 2)


def _discounts_captured(session: Session, policy: str) -> float:
    """Reconstructed from `invoices`, policy-scoped, rather than summing INVOICE_PAID
    events' `discount_captured` payload field as the B7 doc's table literally says. The
    `Event` contract has no `policy` column (FINAL.md section 8.6), and AGENT/BASELINE share
    identical invoice ids, so an INVOICE_PAID event cannot be attributed to one policy over
    the other. `invoices` is policy-scoped and carries exactly what
    api/services/executor.py `_pay_cash` wrote: for a CASH-funded, PAID invoice,
    `amount - paid_amount` is positive when a discount was captured and negative when a
    late penalty was paid instead — a single invoice is settled by exactly one action, so
    it is never both.
    """
    rows = (
        session.query(Invoice.amount, Invoice.paid_amount)
        .filter(
            Invoice.policy == policy,
            Invoice.status == "PAID",
            Invoice.funding_source == "CASH",
            Invoice.paid_amount.isnot(None),
        )
        .all()
    )
    total = sum(
        max(0.0, float(amount) - float(paid_amount)) for amount, paid_amount in rows
    )
    return round(total, 2)


def _shortfall_days(session: Session, policy: str) -> int:
    """Distinct `sim_day` whose closing balance (the latest ledger row posted that day,
    ledger rows within a day are appended in-order — api/services/ledger.py) was < 0."""
    rows = (
        session.query(CashLedger.sim_day, CashLedger.balance)
        .filter(CashLedger.policy == policy)
        .order_by(CashLedger.sim_day.asc(), CashLedger.id.asc())
        .all()
    )
    closing: dict[int, float] = {}
    for sim_day, balance in rows:
        closing[sim_day] = float(balance)  # ascending order — last write per day wins
    return sum(1 for balance in closing.values() if balance < 0)


def _min_cash_seen(session: Session, policy: str) -> float:
    row = (
        session.query(CashLedger.balance)
        .filter(CashLedger.policy == policy)
        .order_by(CashLedger.balance.asc())
        .first()
    )
    return round(float(row[0]), 2) if row is not None else 0.0


def _obligations_missed(session: Session, policy: str) -> int:
    """An obligation "whose due date passed with the balance going negative": for every
    settled obligation, the ledger row this policy posted for it (reason=OBLIGATION,
    ref_id=obligation id — api/services/sim_loop.py step 3) either left the balance
    negative or it did not. Exact, not an approximation from aggregate balances."""
    settled_ids = [
        row[0]
        for row in session.query(Obligation.id).filter(
            Obligation.settled_on.isnot(None)
        )
    ]
    if not settled_ids:
        return 0
    rows = (
        session.query(CashLedger.balance)
        .filter(
            CashLedger.policy == policy,
            CashLedger.reason == "OBLIGATION",
            CashLedger.ref_id.in_(settled_ids),
        )
        .all()
    )
    return sum(1 for (balance,) in rows if float(balance) < 0)


def _avg_supplier_stress(session: Session, policy: str) -> float:
    """Mean `liquidity_stress` weighted by outstanding (OPEN/SCHEDULED) invoice amount for
    this policy. No outstanding invoices is an explicit zero, not an error — a policy with
    nothing left owed has no supplier stress to report."""
    rows = (
        session.query(Invoice.amount, Supplier.liquidity_stress)
        .join(Supplier, Supplier.id == Invoice.supplier_id)
        .filter(Invoice.policy == policy, Invoice.status.in_(("OPEN", "SCHEDULED")))
        .all()
    )
    total_amount = sum(float(amount) for amount, _ in rows)
    if total_amount <= 0:
        return 0.0
    weighted = sum(float(amount) * float(stress) for amount, stress in rows)
    return round(weighted / total_amount, 2)


def _decisions_made(session: Session, policy: str) -> int:
    return session.query(Decision).filter(Decision.policy == policy).count()


def _reoptimizations_triggered(session: Session, policy: str) -> int:
    rows = session.query(Decision.payload).filter(Decision.policy == policy).all()
    return sum(
        1
        for (payload,) in rows
        if (payload or {}).get("trigger", {}).get("type") == "EVENT"
    )


def _policy_metrics(session: Session, policy: str, sim_day: int) -> dict:
    financing_cost = _financing_cost(session, policy)
    penalties_paid = _penalties_paid(session, policy)
    discounts_captured = _discounts_captured(session, policy)
    nwc = net_working_capital_cost(financing_cost, penalties_paid, discounts_captured)
    shortfall_days = _shortfall_days(session, policy)
    obligations_missed = _obligations_missed(session, policy)
    avg_supplier_stress = _avg_supplier_stress(session, policy)
    total_obligations, total_payable_value, total_discount_available = _world_constants(
        session, policy
    )

    hs = health_score(
        shortfall_days=shortfall_days,
        obligations_missed=obligations_missed,
        penalties_paid=penalties_paid,
        discounts_captured=discounts_captured,
        avg_supplier_stress=avg_supplier_stress,
        financing_cost=financing_cost,
        sim_day=sim_day,
        total_obligations=total_obligations,
        total_payable_value=total_payable_value,
        total_discount_available=total_discount_available,
    )

    return {
        "discounts_captured": discounts_captured,
        "financing_cost": financing_cost,
        "penalties_paid": penalties_paid,
        "net_working_capital_cost": nwc,
        "shortfall_days": shortfall_days,
        "min_cash_seen": _min_cash_seen(session, policy),
        "obligations_missed": obligations_missed,
        "avg_supplier_stress": avg_supplier_stress,
        "decisions_made": _decisions_made(session, policy),
        "reoptimizations_triggered": _reoptimizations_triggered(session, policy),
        "health_score": hs,
        "savings_per_day": savings_per_day(nwc, sim_day),
    }


def compute(session: Session, sim_day: int, as_of: date) -> dict:
    """The one place `ComparisonMetrics` is assembled. Validated before return — the
    cheapest bug detector in the project (api/services/state_builder.py's own rule)."""
    agent = _policy_metrics(session, POLICY_AGENT, sim_day)
    baseline = _policy_metrics(session, POLICY_BASELINE, sim_day)
    payload = {
        "sim_day": sim_day,
        "as_of": as_of,
        "agent": agent,
        "baseline": baseline,
        "delta": compute_delta(agent, baseline),
    }
    return ComparisonMetrics.model_validate(payload).model_dump(mode="json")
