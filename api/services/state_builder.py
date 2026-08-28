# api/services/state_builder.py — B4. DB -> State. Single source of truth.
#
# GET /state and build_state() share ONE code path (docs/backend/07-PHASE-B4-state-builder-
# and-engine.md step 1): the route is just `build_state(...).model_dump(mode="json")`. Two
# code paths here is how the engine ends up seeing a world the dashboard is not showing.
#
# Same query rules as B3's GET /state (FINAL.md section 8.2):
#   - invoices, facilities are policy-scoped
#   - invoices: only status in ("OPEN", "SCHEDULED") — decision candidates only
#   - receivables: only status "OPEN"
#   - obligations: unsettled, but NOT date-filtered — the engine needs the full 90-day
#     horizon, and payroll on day 30 is the whole point
from sqlalchemy.orm import Session

from api.errors import HelmError
from api.models import (
    CashLedger,
    Customer,
    Facility,
    Invoice,
    Obligation,
    Receivable,
    SimState,
    Supplier,
)
from api.services.serializers import (
    customer_out,
    facility_out,
    invoice_out,
    obligation_out,
    receivable_out,
    supplier_out,
)
from contracts.schemas import State


def _latest_balance(session: Session, policy: str) -> float:
    # cash_ledger is append-only (CLAUDE.md B3): current cash is the newest row's balance.
    row = (
        session.query(CashLedger)
        .filter(CashLedger.policy == policy)
        .order_by(CashLedger.sim_day.desc(), CashLedger.id.desc())
        .first()
    )
    return float(row.balance) if row is not None else 0.0


def _all_suppliers(session: Session):
    return session.query(Supplier).all()


def _all_customers(session: Session):
    return session.query(Customer).all()


def _open_invoices(session: Session, policy: str):
    return (
        session.query(Invoice)
        .filter(Invoice.policy == policy, Invoice.status.in_(("OPEN", "SCHEDULED")))
        .all()
    )


def _open_receivables(session: Session):
    return session.query(Receivable).filter(Receivable.status == "OPEN").all()


def _unsettled_obligations(session: Session):
    return session.query(Obligation).filter(Obligation.settled_on.is_(None)).all()


def _facilities(session: Session, policy: str):
    return session.query(Facility).filter(Facility.policy == policy).all()


def build_state(session: Session, policy: str) -> State:
    """DB -> validated `State`. The only place `api/` assembles a State object."""
    sim = session.get(SimState, 1)
    if sim is None:
        raise HelmError(
            "NOT_FOUND", "simulation not initialized - call POST /sim/reset first", 404
        )

    payload = {
        "as_of": sim.as_of.isoformat(),
        "sim_day": sim.sim_day,
        "cash_available": round(_latest_balance(session, policy), 2),
        "suppliers": [supplier_out(r) for r in _all_suppliers(session)],
        "customers": [customer_out(r) for r in _all_customers(session)],
        "invoices": [invoice_out(r) for r in _open_invoices(session, policy)],
        "receivables": [receivable_out(r) for r in _open_receivables(session)],
        "obligations": [obligation_out(r) for r in _unsettled_obligations(session)],
        "facilities": [facility_out(r) for r in _facilities(session, policy)],
    }
    # Validate before returning. Always. Cheapest bug detector in the project.
    return State.model_validate(payload)
