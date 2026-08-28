# Phase B1 — Database and Models

**Window:** H+1 → H+3
**Blocks:** B2 (seed), everything after

---

## 1. Goal

SQLAlchemy models matching `FINAL.md` section 9 exactly, a session factory, and a
`create_all` path that rebuilds the schema from scratch in under a second. No migrations
tool — at 24-hour scale, drop-and-recreate is faster and safer than Alembic.

## 2. Files

```
api/db.py            # engine, SessionLocal, get_session dependency, reset_schema()
api/models.py        # all nine tables
api/enums.py         # thin re-export from contracts/enums.py, plus API-only constants
```

## 3. Build steps

### Step 1 — `api/db.py`

```python
# api/db.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from api import config

engine = create_engine(config.DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

class Base(DeclarativeBase):
    pass

def get_session():
    """FastAPI dependency. One session per request, always closed."""
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()

def reset_schema():
    """Drop everything and recreate. This IS our migration strategy."""
    from api import models  # noqa: F401  — registers the tables on Base
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
```

`pool_pre_ping=True` matters: when the Postgres container is restarted at hour 14, the pool
would otherwise hand out dead connections and you would lose fifteen minutes to a confusing
`OperationalError`.

### Step 2 — `api/models.py`

One class per table in section 9. Rules:

- **Column names match the SQL in section 9 exactly.** `facilities.limit_amount`, not `limit`
  (`limit` is a reserved word). The `State` contract calls it `limit`; the mapping from
  `limit_amount` to `limit` happens in `state_builder.py`, phase B4, and nowhere else.
- **Amounts are `Numeric(14, 2)`.** Convert to `float` only at the API boundary.
- **`historical_delays` and `eligible_supplier_ids` are `JSONB`.**
- **`policy` columns on `invoices`, `facilities`, `cash_ledger`** with default `'AGENT'`.
- **Indexes exactly as listed.** Four of them. They cost nothing and the replay query pattern
  hits all four.

Sketch of the two that carry the most risk:

```python
class CashLedger(Base):
    __tablename__ = "cash_ledger"
    id      = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sim_day = mapped_column(Integer, nullable=False)
    date    = mapped_column(Date, nullable=False)
    policy  = mapped_column(Text, nullable=False)
    delta   = mapped_column(Numeric(14, 2), nullable=False)
    balance = mapped_column(Numeric(14, 2), nullable=False)
    reason  = mapped_column(Text, nullable=False)
    ref_id  = mapped_column(Text, nullable=True)
    __table_args__ = (Index("idx_cash_ledger_day", "policy", "sim_day"),)

class Decision(Base):
    __tablename__ = "decisions"
    decision_id = mapped_column(Text, primary_key=True)
    sim_day     = mapped_column(Integer, nullable=False)
    run_at      = mapped_column(Date, nullable=False)
    policy      = mapped_column(Text, nullable=False)
    payload     = mapped_column(JSONB, nullable=False)   # the full DecisionObject
    explanation = mapped_column(JSONB, nullable=True)
    created_at  = mapped_column(DateTime, server_default=func.now(), nullable=False)
    __table_args__ = (Index("idx_decisions_day", "sim_day", "policy"),)
```

**The whole `DecisionObject` is one JSONB column.** Do not normalise `actions` into a table.
It buys nothing at this scale and costs an hour you do not have.

### Step 3 — a `sim_state` singleton

Section 9 does not define one, and you need somewhere to keep the clock. Add a single-row
table. **This is an `api/`-internal table, not a contract change** — it never appears in any
response body, so no announcement is needed.

```python
class SimState(Base):
    __tablename__ = "sim_state"
    id          = mapped_column(Integer, primary_key=True, default=1)
    sim_day     = mapped_column(Integer, nullable=False, default=0)
    as_of       = mapped_column(Date, nullable=False)
    seed        = mapped_column(Integer, nullable=False)
    running     = mapped_column(Boolean, nullable=False, default=False)
    horizon_days= mapped_column(Integer, nullable=False, default=90)
    weights     = mapped_column(JSONB, nullable=False)   # current objective weights
```

Exactly one row, `id = 1`, written by `/sim/reset`. Every read of "what day is it" goes
through this row, never a module-level global — a global will not survive `--reload` and you
will chase a phantom bug for twenty minutes.

### Step 4 — `api/enums.py`

```python
# api/enums.py
from contracts.enums import (          # single source of truth
    ActionType, FundingSource, EventType, EventSource, TriggerType,
    ActionStatus, InvoiceStatus, ReceivableStatus, FacilityType,
    ObligationCategory, SolverMethod, SolverStatus, ReasonCode,
)

POLICY_AGENT    = "AGENT"
POLICY_BASELINE = "BASELINE"
POLICIES        = (POLICY_AGENT, POLICY_BASELINE)
```

Never redefine an enum value locally. If `contracts/enums.py` does not import cleanly, that is
a contract problem to raise out loud, not to route around.

### Step 5 — ID generation

One helper module, one format, used everywhere. IDs are contract surface
(`FINAL.md` section 8, "Universal conventions") and getting them wrong breaks the frontend's
sorting and the explainer's string interpolation.

```python
# api/services/ids.py
def event_id(n: int)    -> str: return f"EVT-{n:04d}"
def decision_id(n: int) -> str: return f"DEC-{n:06d}"
def action_id(n: int)   -> str: return f"ACT-{n:04d}"
def invoice_id(n: int)  -> str: return f"INV-{n:04d}"
def rcv_id(n: int)      -> str: return f"RCV-{n:04d}"
def sup_id(n: int)      -> str: return f"SUP-{n:03d}"
def cus_id(n: int)      -> str: return f"CUS-{n:03d}"
def obl_id(n: int)      -> str: return f"OBL-{n:03d}"
def fac_id(n: int)      -> str: return f"FAC-{n:03d}"
```

Counters come from `SELECT count(*)` on the relevant table inside the same transaction, not
from a Python global.

## 4. Definition of done

- [ ] `python -c "from api.db import reset_schema; reset_schema()"` completes with no error
- [ ] All nine contract tables plus `sim_state` exist in Postgres
- [ ] Column names and types match `FINAL.md` section 9 exactly (compare side by side, once)
- [ ] All four indexes present
- [ ] `policy` column present on `invoices`, `facilities`, `cash_ledger`
- [ ] `api/enums.py` imports cleanly from `contracts/enums.py`
- [ ] API still boots; every route still returns its fixture

## 5. Verify

```bash
python -c "from api.db import reset_schema; reset_schema(); print('schema ok')"

docker compose exec db psql -U helm -d helm -c '\dt'
docker compose exec db psql -U helm -d helm -c '\d invoices'
docker compose exec db psql -U helm -d helm -c '\d cash_ledger'
docker compose exec db psql -U helm -d helm -c '\di'

curl -s localhost:8000/api/health
```

`\d invoices` must show `policy` and `\di` must show the four `idx_*` indexes. If the schema
diverges from section 9 now, every downstream phase inherits the divergence.
