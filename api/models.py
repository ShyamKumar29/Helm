# api/models.py — SQLAlchemy ORM, matching FINAL.md section 9 exactly. B1.
#
# Column names match the SQL in FINAL.md section 9 verbatim, including
# `facilities.limit_amount` (not `limit` — reserved word). The State contract's
# `limit` field is mapped from `limit_amount` in state_builder.py (B4), nowhere else.
#
# Amounts are NUMERIC(14,2) here; cast to float only at the API boundary.
from sqlalchemy import (
    REAL,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import mapped_column

from api.db import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    id = mapped_column(Text, primary_key=True)
    name = mapped_column(Text, nullable=False)
    criticality = mapped_column(REAL, nullable=False)
    liquidity_stress = mapped_column(REAL, nullable=False)
    supplier_finance_eligible = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint("criticality BETWEEN 0 AND 1", name="ck_suppliers_criticality"),
        CheckConstraint(
            "liquidity_stress BETWEEN 0 AND 1", name="ck_suppliers_liquidity_stress"
        ),
    )


class Customer(Base):
    __tablename__ = "customers"

    id = mapped_column(Text, primary_key=True)
    name = mapped_column(Text, nullable=False)
    mean_delay_days = mapped_column(REAL, nullable=False)
    std_delay_days = mapped_column(REAL, nullable=False)
    on_time_probability = mapped_column(REAL, nullable=False)
    historical_delays = mapped_column(JSONB, nullable=False)


class Invoice(Base):
    __tablename__ = "invoices"

    # Composite PK (id, policy), not just `id`. FINAL.md section 9 writes `id TEXT PRIMARY
    # KEY`, but section 13/CLAUDE.md rule B4 require the *same* invoice id duplicated once
    # per policy ("Seed both policies identically ... identical copies of invoices").
    # A single-column PK makes that insert impossible — this is a B1 schema defect, fixed
    # here inside api/ ownership; no column or JSON contract field changes.
    id = mapped_column(Text, primary_key=True)
    supplier_id = mapped_column(Text, ForeignKey("suppliers.id"), nullable=False)
    amount = mapped_column(Numeric(14, 2), nullable=False)
    issue_date = mapped_column(Date, nullable=False)
    due_date = mapped_column(Date, nullable=False)
    discount_pct = mapped_column(REAL, nullable=True)
    discount_until = mapped_column(Date, nullable=True)
    penalty_bps_per_day = mapped_column(REAL, nullable=False, default=0)
    max_delay_days = mapped_column(Integer, nullable=False, default=0)
    status = mapped_column(Text, nullable=False, default="OPEN")
    paid_on = mapped_column(Date, nullable=True)
    paid_amount = mapped_column(Numeric(14, 2), nullable=True)
    funding_source = mapped_column(Text, nullable=True)
    policy = mapped_column(Text, primary_key=True, default="AGENT")

    __table_args__ = (Index("idx_invoices_status", "policy", "status"),)


class Receivable(Base):
    __tablename__ = "receivables"

    id = mapped_column(Text, primary_key=True)
    customer_id = mapped_column(Text, ForeignKey("customers.id"), nullable=False)
    amount = mapped_column(Numeric(14, 2), nullable=False)
    expected_date = mapped_column(Date, nullable=False)
    actual_date = mapped_column(Date, nullable=True)
    status = mapped_column(Text, nullable=False, default="OPEN")


class Obligation(Base):
    __tablename__ = "obligations"

    id = mapped_column(Text, primary_key=True)
    label = mapped_column(Text, nullable=False)
    category = mapped_column(Text, nullable=False)
    amount = mapped_column(Numeric(14, 2), nullable=False)
    due_date = mapped_column(Date, nullable=False)
    hard = mapped_column(Boolean, nullable=False, default=True)
    settled_on = mapped_column(Date, nullable=True)


class Facility(Base):
    __tablename__ = "facilities"

    # Composite PK (id, policy) — same reasoning as Invoice above: FAC-001/FAC-002 must
    # exist once per policy with identical ids.
    id = mapped_column(Text, primary_key=True)
    type = mapped_column(Text, nullable=False)
    limit_amount = mapped_column(Numeric(14, 2), nullable=False)
    drawn = mapped_column(Numeric(14, 2), nullable=False, default=0)
    apr_pct = mapped_column(REAL, nullable=False)
    min_draw = mapped_column(Numeric(14, 2), nullable=False, default=0)
    repayment_days = mapped_column(Integer, nullable=False)
    eligible_supplier_ids = mapped_column(JSONB, nullable=True)
    policy = mapped_column(Text, primary_key=True, default="AGENT")


class CashLedger(Base):
    __tablename__ = "cash_ledger"

    id = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sim_day = mapped_column(Integer, nullable=False)
    date = mapped_column(Date, nullable=False)
    policy = mapped_column(Text, nullable=False)
    delta = mapped_column(Numeric(14, 2), nullable=False)
    balance = mapped_column(Numeric(14, 2), nullable=False)
    reason = mapped_column(Text, nullable=False)
    ref_id = mapped_column(Text, nullable=True)

    __table_args__ = (Index("idx_cash_ledger_day", "policy", "sim_day"),)


class Event(Base):
    __tablename__ = "events"

    event_id = mapped_column(Text, primary_key=True)
    sim_day = mapped_column(Integer, nullable=False)
    date = mapped_column(Date, nullable=False)
    type = mapped_column(Text, nullable=False)
    source = mapped_column(Text, nullable=False)
    payload = mapped_column(JSONB, nullable=False)
    materiality_score = mapped_column(REAL, nullable=True)
    triggered_reoptimization = mapped_column(Boolean, nullable=False, default=False)
    triggered_decision_id = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (Index("idx_events_day", "sim_day"),)


class Decision(Base):
    __tablename__ = "decisions"

    decision_id = mapped_column(Text, primary_key=True)
    sim_day = mapped_column(Integer, nullable=False)
    run_at = mapped_column(Date, nullable=False)
    policy = mapped_column(Text, nullable=False)
    payload = mapped_column(JSONB, nullable=False)  # the full DecisionObject
    explanation = mapped_column(JSONB, nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now(), nullable=False)

    __table_args__ = (Index("idx_decisions_day", "sim_day", "policy"),)


# --- api/-internal — not a contract table, never appears in a response body. ---
class SimState(Base):
    """Singleton clock row. Exactly one record, id=1, written by POST /sim/reset.

    The CHECK constraint below makes a second authoritative row impossible at the
    DB level, not just by convention — no `SELECT count(*)` race can slip past it.
    """

    __tablename__ = "sim_state"

    id = mapped_column(Integer, primary_key=True, default=1)
    sim_day = mapped_column(Integer, nullable=False, default=0)
    as_of = mapped_column(Date, nullable=False)
    seed = mapped_column(Integer, nullable=False)
    running = mapped_column(Boolean, nullable=False, default=False)
    horizon_days = mapped_column(Integer, nullable=False, default=90)
    weights = mapped_column(JSONB, nullable=False)  # current objective weights

    __table_args__ = (CheckConstraint("id = 1", name="ck_sim_state_singleton"),)
