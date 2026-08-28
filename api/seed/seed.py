# api/seed/seed.py — B2. Inserts a WorldSpec into Postgres through the B1 session factory.
#
# `seed_world()` is the only DB-touching function in this package: build_world() and
# planted.apply() stay pure (no session, no engine import), matching
# docs/backend/05-PHASE-B2-seed-data.md step 3's isolation goal.
#
# Seeding order follows FK dependency: suppliers, customers, facilities, obligations,
# invoices, receivables, cash_ledger, sim_state. Suppliers/customers/receivables/obligations
# are shared single copies; invoices/facilities/cash_ledger are duplicated per policy
# (13-SEED-DATA-SPEC.md section 10 rule 3).
from __future__ import annotations

from datetime import date, datetime

from api import config
from api.db import SessionLocal, reset_schema
from api.enums import POLICIES
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
from api.seed import planted
from api.seed.generate import build_world


def _parse_date(d: str | date) -> date:
    if isinstance(d, date):
        return d
    return datetime.strptime(d, "%Y-%m-%d").date()


def seed_world(seed: int | None = None, start_date: str | date | None = None) -> dict:
    """Drop and recreate the schema, then build and persist a deterministic world.

    Safe to call repeatedly (that IS the reset mechanism) — every call starts from a clean
    schema, so there is never a duplicate-ID conflict from a previous run.
    """
    seed = config.SIM_SEED if seed is None else seed
    start = _parse_date(config.SIM_START_DATE if start_date is None else start_date)

    reset_schema()

    world = build_world(seed, start)
    world = planted.apply(world)

    session = SessionLocal()
    try:
        # ---- shared, single-copy tables ------------------------------------------------
        session.add_all(Supplier(**s) for s in world["suppliers"])
        session.add_all(Customer(**c) for c in world["customers"])
        session.add_all(Obligation(**o) for o in world["obligations"])
        session.add_all(Receivable(**r) for r in world["receivables"])
        session.flush()  # suppliers/customers committed before FK-dependent inserts below

        # ---- policy-scoped tables: one identical copy per policy -----------------------
        for policy in POLICIES:
            session.add_all(Invoice(policy=policy, **inv) for inv in world["invoices"])
            session.add_all(
                Facility(policy=policy, **fac) for fac in world["facilities"]
            )
            session.add(
                CashLedger(
                    sim_day=0,
                    date=start,
                    policy=policy,
                    delta=world["opening_cash"],
                    balance=world["opening_cash"],
                    reason="OPENING_BALANCE",
                    ref_id=None,
                )
            )

        # ---- sim clock singleton ---------------------------------------------------------
        session.add(
            SimState(
                id=1,
                sim_day=0,
                as_of=start,
                seed=seed,
                running=False,
                horizon_days=config.HORIZON_DAYS,
                weights=world["weights"],
            )
        )

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    total_payable_value = sum(inv["amount"] for inv in world["invoices"])
    total_discount_available = sum(
        inv["amount"] * inv["discount_pct"] / 100
        for inv in world["invoices"]
        if inv["discount_pct"] is not None
    )

    return dict(
        sim_day=0,
        as_of=start.isoformat(),
        seed=seed,
        counts=dict(
            suppliers=len(world["suppliers"]),
            customers=len(world["customers"]),
            obligations=len(world["obligations"]),
            receivables=len(world["receivables"]),
            invoices_per_policy=len(world["invoices"]),
            facilities_per_policy=len(world["facilities"]),
        ),
        # World constants per 13-SEED-DATA-SPEC.md section 10 rule 5. `sim_state` has no
        # columns for these (B1's schema, frozen) so they are recomputed on demand by
        # whichever later phase needs them (health score, B7) rather than cached here.
        world_constants=dict(
            total_obligations=len(world["obligations"]),
            total_payable_value=round(total_payable_value, 2),
            total_discount_available=round(total_discount_available, 2),
        ),
    )


if __name__ == "__main__":
    import json

    print(json.dumps(seed_world(), indent=2))
