# Phase B4 — State Builder and the Engine Gateway

**Window:** H+7 → H+9
**Unblocks:** Shyam gets a real `State` to test against; B5 can call `decide()`

---

## 1. Goal

One function that turns the database into a `State` object, and one module that is the sole
import site for `engine/`, complete with timeout, exception handling and fixture fallback.

After this phase, calling the engine from anywhere in `api/` is a single line that cannot
crash the API and cannot hang the demo.

## 2. Files

```
api/services/state_builder.py     # DB -> State
api/services/engine_gateway.py    # the only import of engine/
api/routers/decisions.py          # POST /decide, POST /weights
```

## 3. Build steps

### Step 1 — `state_builder.py`

```python
# api/services/state_builder.py
from contracts.schemas import State
from api.services import serializers as ser

def build_state(session, policy: str) -> State:
    sim = session.get(SimState, 1)
    cash = latest_balance(session, policy)
    payload = {
        "as_of": sim.as_of.isoformat(),
        "sim_day": sim.sim_day,
        "cash_available": ser.money(cash),
        "suppliers":   [ser.supplier_out(r)   for r in all_suppliers(session)],
        "customers":   [ser.customer_out(r)   for r in all_customers(session)],
        "invoices":    [ser.invoice_out(r)    for r in open_invoices(session, policy)],
        "receivables": [ser.receivable_out(r) for r in open_receivables(session)],
        "obligations": [ser.obligation_out(r) for r in unsettled_obligations(session)],
        "facilities":  [ser.facility_out(r)   for r in facilities(session, policy)],
    }
    return State.model_validate(payload)
```

**`GET /state` and `build_state()` must return the same thing.** Implement the route as
`build_state(...).model_dump(mode="json")` so there is literally one code path. Two code paths
here is how you end up with the engine seeing a world the dashboard is not showing.

Rules:

- Always policy-scoped for invoices and facilities.
- Only `status in ("OPEN", "SCHEDULED")` invoices.
- Only `status == "OPEN"` receivables.
- Only unsettled obligations, but **do not** filter by date — the engine needs the full
  90-day horizon of future obligations, and payroll on day 30 is the whole point.
- Validate with the Pydantic model before returning. Always. It is the cheapest bug detector
  in the project.

### Step 2 — `engine_gateway.py`, complete version

```python
# api/services/engine_gateway.py
import json, logging, pathlib
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from api import config

log = logging.getLogger(__name__)
_FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
_POOL = ThreadPoolExecutor(max_workers=2)

try:
    from engine.decide import decide as _decide, forecast as _forecast
    ENGINE_AVAILABLE = True
except Exception as e:
    log.warning("engine not importable, serving fixtures: %s", e)
    ENGINE_AVAILABLE = False

def _fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))

def decide(state, weights=None, previous=None, trigger=None) -> tuple[dict, str]:
    """Returns (decision_dict, source) where source is 'engine' | 'fixture' | 'degraded'."""
    if not ENGINE_AVAILABLE:
        return _fixture("decision.sample.json"), "fixture"
    budget_s = (config.SOLVER_TIMEOUT_MS + 1500) / 1000.0   # engine's own 2s + our margin
    fut = _POOL.submit(_decide, state, weights=weights, previous=previous, trigger=trigger)
    try:
        result = fut.result(timeout=budget_s)
    except FuturesTimeout:
        log.error("engine.decide exceeded %.1fs budget", budget_s)
        return _fixture("decision.sample.json"), "degraded"
    except Exception:
        log.exception("engine.decide raised")
        return _fixture("decision.sample.json"), "degraded"
    return _as_dict(result), "engine"
```

Three things this buys:

1. **The API never hangs.** The engine has its own 2-second internal timeout; this is the
   outer guard for the case where that timeout itself fails.
2. **The API never 500s because of the engine.** A raised exception degrades to the last
   known-good shape and logs loudly.
3. **One place to change** when Shyam changes something.

`_as_dict` accepts either a Pydantic model or a dict, because the engine may return either
depending on how far along it is.

### Step 3 — validate what comes back, and say so out loud when it fails

```python
from contracts.schemas import DecisionObject

def validated(decision: dict) -> dict:
    try:
        return DecisionObject.model_validate(decision).model_dump(mode="json")
    except Exception:
        log.exception("engine returned an invalid DecisionObject")
        raise
```

When this fires, **do not patch the decision in `api/`.** Say it out loud to Shyam with the
field name. Patching it here means the engine's own tests keep passing while the real system
is wrong, which is the worst possible state to be in at hour 16.

The one exception, and it is explicitly allowed: **`api/` may fill `decision_id`, `run_at`,
`sim_day` and `policy`** if the engine leaves them blank, because those are simulation facts
the engine cannot know. Nothing else.

### Step 4 — `POST /decide`

```
body: {"weights": {...} | null, "reason": "MANUAL"}
```

1. `build_state(session, "AGENT")`
2. previous = newest AGENT decision payload, or `None`
3. `trigger = {"type": "MANUAL", "event_id": null, "materiality_score": null, "description": reason}`
4. call the gateway, validate, stamp the simulation fields
5. persist to `decisions`
6. broadcast on the `decision` channel (from B6; a no-op stub until then)
7. return the decision

### Step 5 — `POST /weights`

Persist the new weights on the `sim_state` row, then do exactly what `/decide` does with
`trigger.type = "MANUAL"` and a description naming the changed weight. Return
`{"weights": {...}, "decision": {...}}`.

This is the route behind the judge-facing sliders at 4:00 in the demo script. It must be fast
— it is called on slider release and the judge is watching. Budget: under 1.5 seconds
end-to-end, which the engine's 2-second cap already threatens. If it feels slow, ask Shyam
out loud to drop `n_paths` to 500; nobody can see the difference.

### Step 6 — the explanation attach, non-blocking and optional

After persisting a decision, try to attach an explanation:

```python
try:
    exp = httpx.post(f"http://127.0.0.1:8000/api/explain/{decision_id}",
                     json={"mode": config.EXPLAINER_MODE}, timeout=3.0).json()
    session.execute(update(Decision).where(...).values(explanation=exp))
except Exception:
    log.warning("explainer unavailable, decision %s has no explanation", decision_id)
```

Never let this fail the request. `explanation: null` renders fine; a 500 does not.

## 4. Definition of done

- [ ] `build_state()` output validates against `contracts.schemas.State`
- [ ] `GET /state` and `build_state()` share one code path
- [ ] Renaming `engine/` to `engine_off/` leaves the API booting and `/decide` returning the
      fixture with `source = "fixture"`
- [ ] An engine that sleeps 10 seconds is cut off by the gateway budget, logged, and degraded
- [ ] An engine that raises is caught, logged, and degraded
- [ ] `POST /decide` persists a row in `decisions` and returns a validated `DecisionObject`
- [ ] `POST /weights` updates `sim_state.weights` and returns a fresh decision
- [ ] Explainer being absent leaves `explanation: null` and no error

## 5. Verify

```bash
curl -s -X POST localhost:8000/api/decide \
  -H 'content-type: application/json' -d '{"weights":null,"reason":"MANUAL"}' > /tmp/dec.json

python - <<'PY'
import json
from contracts.schemas import DecisionObject
d = json.load(open("/tmp/dec.json"))
DecisionObject.model_validate(d)
assert all(len(a["rejected_alternatives"]) >= 1 for a in d["actions"]), "PS req 7 violated"
print("decision validates,", len(d["actions"]), "actions")
PY

# engine-absent drill
mv engine engine_off && curl -s localhost:8000/api/health && \
  curl -s -X POST localhost:8000/api/decide -H 'content-type: application/json' -d '{}' | head -c 120
mv engine_off engine
```

Run the engine-absent drill at least once. It is the whole reason the gateway exists, and you
want to have seen it work before it matters.
