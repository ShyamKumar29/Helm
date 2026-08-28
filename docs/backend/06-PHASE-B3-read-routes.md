# Phase B3 — Read Routes on Real Data

**Window:** H+5 → H+7
**Unblocks:** Person C flips `USE_MOCK=false` at checkpoint I2 (H+8)

---

## 1. Goal

Replace the fixture stubs in the read routes with real queries against Postgres, **without
changing a single response shape.** Person C should notice nothing except that the numbers
start moving.

## 2. Files

```
api/routers/state.py         # /state, /forecast   — real
api/routers/decisions.py     # /decisions, /decisions/{id}  — real
api/routers/events.py        # GET /events — real
api/routers/compare.py       # /compare — still fixture-shaped until B7
api/services/serializers.py  # row -> contract dict, one place
```

## 3. Build steps

### Step 1 — `serializers.py` is the only place a DB row becomes JSON

Every `Numeric` becomes a `float` rounded to 2 decimals here. Every `Date` becomes an ISO
string here. Every optional field is emitted as `null`, never omitted — the contract says the
frontend must not have to check `undefined`.

```python
# api/services/serializers.py
def money(v) -> float:
    return round(float(v), 2)

def iso(d) -> str | None:
    return d.isoformat() if d else None

def invoice_out(row) -> dict:
    return {
        "id": row.id,
        "supplier_id": row.supplier_id,
        "amount": money(row.amount),
        "issue_date": iso(row.issue_date),
        "due_date": iso(row.due_date),
        "discount_pct": float(row.discount_pct) if row.discount_pct is not None else None,
        "discount_until": iso(row.discount_until),
        "penalty_bps_per_day": float(row.penalty_bps_per_day),
        "max_delay_days": int(row.max_delay_days),
        "status": row.status,
    }
```

Note `facilities`: the DB column is `limit_amount`, the contract field is `limit`. The rename
happens here and nowhere else.

```python
def facility_out(row) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "limit": money(row.limit_amount),      # <- the rename, single site
        "drawn": money(row.drawn),
        "apr_pct": float(row.apr_pct),
        "min_draw": money(row.min_draw),
        "repayment_days": int(row.repayment_days),
        "eligible_supplier_ids": row.eligible_supplier_ids,   # null or list
    }
```

### Step 2 — `GET /state`

Assemble the `State` contract (`FINAL.md` section 8.2) for the requested policy:

- `as_of`, `sim_day` from the `sim_state` row
- `cash_available` = `balance` of the newest `cash_ledger` row for that policy
- `suppliers`, `customers` — shared, all rows
- `invoices` — **policy-scoped**, status in `("OPEN", "SCHEDULED")` only
- `receivables` — shared, status `"OPEN"` only
- `obligations` — shared, `settled_on is null`
- `facilities` — policy-scoped

The status filters matter. `FINAL.md` section 8.2 says only OPEN and SCHEDULED invoices are
decision candidates; handing the engine PAID invoices makes it emit HOLD actions for things
that no longer exist, and the frontend then renders dead cards.

Validate before returning, once:

```python
from contracts.schemas import State
return State.model_validate(payload).model_dump(mode="json")
```

Cheap, and it catches every field-name drift the moment it happens rather than at H+12.

### Step 3 — `GET /forecast`

Two acceptable implementations, in preference order:

1. **Call the engine gateway** (`forecast(state, horizon_days)`), returning the `Forecast`
   contract directly. Correct, and what the route is for.
2. **Serve the forecast embedded in the newest AGENT decision.** Cheaper, and indistinguishable
   on screen. This is scope cut #4 in `02-PHASE-PLAN.md`.

Until phase B4 lands the gateway, keep serving `forecast.sample.json`. The route already has
the right shape, so nothing downstream changes when you swap the internals.

### Step 4 — `GET /decisions` and `GET /decisions/{id}`

```sql
SELECT payload, explanation FROM decisions
WHERE policy = :policy ORDER BY sim_day DESC, created_at DESC LIMIT :limit
```

Return the stored `payload` JSONB **as-is**, with `explanation` merged into it:

```python
obj = row.payload
obj["explanation"] = row.explanation      # null until the explainer fills it
return obj
```

Do not reshape, do not re-round, do not add fields. The payload was written by the engine and
already validated on the way in (phase B5). Touching it here creates a class of bug where the
stored decision and the served decision differ, which is unfindable at 3am.

`GET /decisions/{decision_id}` on an unknown id raises `HelmError("NOT_FOUND", ..., 404)`.

### Step 5 — `GET /events`

```sql
SELECT * FROM events ORDER BY sim_day DESC, created_at DESC LIMIT :limit
```

Serialize to the `Event` contract (section 8.6). `materiality_score` may be `null` for
system events; emit the key with `null`, never omit it.

### Step 6 — `GET /compare`

Leave it on the fixture until B7. It is the one read route whose real implementation depends
on the baseline agent existing. Shape is already right, so Person C's scoreboard renders.

## 4. What NOT to do in this phase

- Do not compute a forecast in `api/`. The engine owns it.
- Do not compute `health_score` yet. That is B7, and it needs baseline data to be meaningful.
- Do not add pagination, filtering or sorting beyond what section 10 specifies. Every extra
  query parameter is a thing Person C has to discover.
- Do not cache. At this data size Postgres answers in single-digit milliseconds and a stale
  cache during a live demo is a category of bug you cannot afford.

## 5. Definition of done

- [ ] `/state?policy=AGENT` and `?policy=BASELINE` both return validated `State` objects
- [ ] `State.invoices` contains only OPEN/SCHEDULED, policy-scoped
- [ ] `cash_available` matches the newest `cash_ledger` balance for that policy
- [ ] `facilities[].limit` is present (not `limit_amount`) — the rename works
- [ ] `/decisions` returns newest first and respects `limit`
- [ ] `/decisions/{unknown}` returns a 404 in the error envelope
- [ ] `/events` returns newest first with `materiality_score` present-or-null
- [ ] Every response validates against `contracts/schemas.py`
- [ ] Person C confirms out loud that `USE_MOCK=false` works against your server

## 6. Verify

```bash
curl -s "localhost:8000/api/state?policy=AGENT" > /tmp/state.json
python - <<'PY'
import json
from contracts.schemas import State
State.model_validate(json.load(open("/tmp/state.json")))
print("state validates")
PY

curl -s "localhost:8000/api/state?policy=BASELINE" | python -c "import json,sys; s=json.load(sys.stdin); print(s['cash_available'], len(s['invoices']))"

curl -s "localhost:8000/api/decisions?policy=AGENT&limit=5" | python -c "import json,sys; print(len(json.load(sys.stdin)))"

curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/api/decisions/DEC-999999   # 404
curl -s localhost:8000/api/decisions/DEC-999999 | grep -q '"error"' && echo "envelope ok"
```
