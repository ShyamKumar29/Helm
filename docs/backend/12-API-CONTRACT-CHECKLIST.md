# 12 — API Contract Checklist

Keep this open in a tab all night. Every route, its exact shape, the phase that makes it real,
and a curl that proves it.

**The shapes are frozen at H+1 (`FINAL.md` section 10). Nothing in this file may change a
shape.** If a shape is wrong, it is a contract change: say it out loud, get agreement, log it
in `contracts/CHANGELOG.md`, tell everyone to pull.

---

## 1. The routes

| # | Method | Path | Real in | Returns |
|---|---|---|---|---|
| 1 | POST | `/api/sim/reset` | B5 | `{"sim_day":0,"as_of":"2026-03-01"}` |
| 2 | POST | `/api/sim/step` | B5 | `{"sim_day","events":[Event],"decisions":[DecisionObject]}` |
| 3 | POST | `/api/sim/play` | B8 | `202`, streams on WS |
| 4 | POST | `/api/sim/pause` | B8 | `{"sim_day","paused":true}` |
| 5 | GET | `/api/sim/status` | B5 | `{"sim_day","as_of","running","horizon_days"}` |
| 6 | GET | `/api/state?policy=` | B3 | `State` |
| 7 | GET | `/api/forecast?horizon=&policy=` | B4 | `Forecast` |
| 8 | GET | `/api/decisions?policy=&limit=` | B3 | `DecisionObject[]`, newest first |
| 9 | GET | `/api/decisions/{id}` | B3 | `DecisionObject` with `explanation` |
| 10 | GET | `/api/events?limit=` | B3 | `Event[]`, newest first |
| 11 | GET | `/api/compare` | B7 | `ComparisonMetrics` |
| 12 | POST | `/api/decide` | B4 | `DecisionObject` |
| 13 | POST | `/api/events` | B6 | `{"event":Event,"decision":DecisionObject\|null}` |
| 14 | POST | `/api/weights` | B4 | `{"weights":{...},"decision":DecisionObject}` |
| 15 | POST | `/api/execute/{decision_id}` | B5 | `{"executed":7,"escalated":1}` |
| 16 | WS | `/api/stream` | B6 | frames: `{"channel","sim_day","data"}` |
| — | GET | `/api/health` | B0 | `{"ok":true}` (ours, not in the contract) |
| — | POST | `/api/explain/{id}` | Person C | `Explanation` — mounted, not owned |
| — | POST | `/api/whatif` | Person C | what-if bundle — mounted, not owned |

Rows 17 and 18 belong to `explainer/`. Person B mounts them at H+1 and never touches them.

## 2. Invariants that must hold on every response

- [ ] Money is a plain float, rounded to 2 decimals, no currency field
- [ ] Dates are ISO `"YYYY-MM-DD"` strings, no timezone, no datetime
- [ ] Optional fields are present with `null`, **never omitted**
- [ ] IDs match the zero-padded prefixed format (`INV-0001`, `DEC-000007`, `SUP-001`)
- [ ] All keys are `snake_case` — never camelCase, even in a nested payload
- [ ] Enum values are exactly the strings in `contracts/enums.py`
- [ ] Errors are `{"error":{"code","message","detail"}}` — no exceptions, no HTML
- [ ] `sim_day` is an int starting at 0

## 3. Per-response contract rules worth re-reading at hour 15

**`State` (route 6)**
- `invoices` policy-scoped, status `OPEN` or `SCHEDULED` only
- `receivables` status `OPEN` only
- `facilities[].limit` — the DB column is `limit_amount`; the rename happens in `serializers.py`
- `facilities[].eligible_supplier_ids` is `null` for a bank line, a list for supplier finance

**`Forecast` (route 7)**
- `buckets` has exactly `horizon_days + 1` entries, `day_offset` from 0 to `horizon_days`
- `deployable_cash >= 0` always
- `buffer_required = max(0, cash_available - deployable_cash)`

**`DecisionObject` (routes 8, 9, 12, 13, 14)**
- one action per open invoice, `HOLD` explicit — never an absent entry
- `rejected_alternatives` has **at least one** entry per action — PS requirement 7
- `delta <= 0` on every rejected alternative
- `funding_source: "CASH"` implies `facility_id: null`
- `explanation` is `null` from the engine; `api/` fills it after the explainer answers
- `policy` is `"AGENT"` or `"BASELINE"`, and both use this identical shape

**`Event` (routes 10, 13)**
- payload shape is frozen per type — `FINAL.md` section 8.6, the table
- `materiality_score` may be `null` for system events, but the key is always present

**`ComparisonMetrics` (route 11)**
- `net_working_capital_cost = financing_cost + penalties_paid - discounts_captured`
- `health_score` is an int in `[0, 100]`
- `savings_per_day = -net_working_capital_cost / max(sim_day, 1)`
- `delta` carries all four of `net_working_capital_cost`, `shortfall_days`,
  `obligations_missed`, `health_score`

**WebSocket (route 16)**
- envelope is exactly `{"channel","sim_day","data"}` — no extra top-level keys
- channels are exactly `event`, `decision`, `metrics`, `forecast`, `sim`, `log`
- `log.data` is `{"level","text"}`
- a snapshot (`sim`, `metrics`, `forecast`) is sent on connect

## 4. The smoke script

Save as `scripts/smoke.sh`. Run it after every phase and before every checkpoint.

```bash
#!/usr/bin/env bash
set -uo pipefail
API=localhost:8000/api
ok=0; fail=0

check () {  # check <name> <curl-args...>
  local name="$1"; shift
  local code
  code=$(curl -s -o /tmp/out.json -w '%{http_code}' "$@")
  if [ "$code" = "200" ] || [ "$code" = "202" ]; then
    echo "  ok   $name ($code)"; ok=$((ok+1))
  else
    echo "  FAIL $name ($code)"; head -c 200 /tmp/out.json; echo; fail=$((fail+1))
  fi
}

J='content-type: application/json'

check health          $API/health
check sim/reset  -X POST $API/sim/reset  -H "$J" -d '{"seed":42,"start_date":"2026-03-01"}'
check sim/status      $API/sim/status
check state           "$API/state?policy=AGENT"
check state-baseline  "$API/state?policy=BASELINE"
check forecast        "$API/forecast?horizon=90&policy=AGENT"
check sim/step   -X POST $API/sim/step -H "$J" -d '{"days":1}'
check decide     -X POST $API/decide   -H "$J" -d '{"weights":null,"reason":"MANUAL"}'
check decisions       "$API/decisions?policy=AGENT&limit=5"
check events          "$API/events?limit=20"
check compare         $API/compare
check weights    -X POST $API/weights  -H "$J" \
  -d '{"discount":1.0,"financing_cost":1.0,"penalty":1.0,"liquidity_risk":1.5,"supplier_stress":0.8}'
check inject     -X POST $API/events   -H "$J" -d '{
  "type":"RECEIVABLE_DELAYED","source":"JUDGE_INJECTED",
  "payload":{"receivable_id":"RCV-0004","new_expected_date":"2026-04-03","delay_days":21}}'

echo "  ---- $ok ok, $fail failed"
[ "$fail" -eq 0 ]
```

## 5. The validation script

Shapes, not status codes. Run before each checkpoint.

```python
# scripts/validate_shapes.py
import json, urllib.request
from contracts.schemas import State, Forecast, DecisionObject, Event, ComparisonMetrics

API = "http://localhost:8000/api"
get = lambda p: json.loads(urllib.request.urlopen(API + p).read())

State.model_validate(get("/state?policy=AGENT"));            print("State ok")
State.model_validate(get("/state?policy=BASELINE"));         print("State(baseline) ok")
Forecast.model_validate(get("/forecast?horizon=90"));        print("Forecast ok")
ComparisonMetrics.model_validate(get("/compare"));           print("ComparisonMetrics ok")

for d in get("/decisions?policy=AGENT&limit=5"):
    DecisionObject.model_validate(d)
    assert all(len(a["rejected_alternatives"]) >= 1 for a in d["actions"]), "PS req 7"
    assert all(a["facility_id"] is None
               for a in d["actions"] if a["funding_source"] == "CASH"), "CASH implies null facility"
print("DecisionObject ok")

for e in get("/events?limit=20"):
    Event.model_validate(e)
    assert "materiality_score" in e, "key must be present even when null"
print("Event ok")
```

## 6. Route-by-route tick list

Tick when the route is real, validated, and error-enveloped.

```
[ ] 1  POST /api/sim/reset          [ ] 9  GET  /api/decisions/{id}
[ ] 2  POST /api/sim/step           [ ] 10 GET  /api/events
[ ] 3  POST /api/sim/play           [ ] 11 GET  /api/compare
[ ] 4  POST /api/sim/pause          [ ] 12 POST /api/decide
[ ] 5  GET  /api/sim/status         [ ] 13 POST /api/events
[ ] 6  GET  /api/state              [ ] 14 POST /api/weights
[ ] 7  GET  /api/forecast           [ ] 15 POST /api/execute/{id}
[ ] 8  GET  /api/decisions          [ ] 16 WS   /api/stream
```
