# 14 — Testing and Verification

Not a test suite. A set of gates that catch the failures that actually kill hackathon demos.

**Time budget: 45 minutes total across the whole night.** Anything more is time stolen from
the seed data, which matters more.

---

## 1. What is worth testing, and what is not

| Worth it | Not worth it |
|---|---|
| Every response validates against `contracts/schemas.py` | Unit tests on serializers |
| `POST /sim/reset` is deterministic | Mocking the engine |
| The engine-absent and explainer-absent drills | Coverage percentage |
| Cash ledger reconciles to the balance | Testing SQLAlchemy |
| A 90-day replay completes without an exception | Property-based testing |
| The four chaos presets fire cleanly | Testing FastAPI's routing |
| The agent beats the baseline on all three headlines | Load testing |

The failure mode of a hackathon backend is not a wrong calculation. It is **a crash during the
demo** and **a shape the frontend cannot render**. Both of those are caught by the list on the
left, cheaply.

## 2. The three scripts

Put them in `scripts/`. They are the whole test strategy.

- **`scripts/smoke.sh`** — every route answers with 200/202. Full listing in
  `12-API-CONTRACT-CHECKLIST.md` §4. Run after every phase.
- **`scripts/validate_shapes.py`** — every response validates against the Pydantic models,
  plus the contract invariants. Full listing in `12-API-CONTRACT-CHECKLIST.md` §5. Run before
  every checkpoint.
- **`scripts/replay_check.py`** — reset, replay 90 days, assert the agent wins. Below.

```python
# scripts/replay_check.py
import json, time, urllib.request

API = "http://localhost:8000/api"

def post(p, body=None):
    req = urllib.request.Request(API + p, method="POST",
                                 data=json.dumps(body or {}).encode(),
                                 headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(req).read())

def get(p):
    return json.loads(urllib.request.urlopen(API + p).read())

t0 = time.time()
post("/sim/reset", {"seed": 42, "start_date": "2026-03-01"})
post("/sim/step", {"days": 90})
elapsed = time.time() - t0

c = get("/compare")
a, b = c["agent"], c["baseline"]

assert a["net_working_capital_cost"] < b["net_working_capital_cost"], "agent does not win on cost"
assert a["shortfall_days"]      <= b["shortfall_days"],      "agent has more shortfall days"
assert a["obligations_missed"]  <= b["obligations_missed"],  "agent missed more obligations"
assert a["health_score"]         > b["health_score"],        "agent health not above baseline"
assert elapsed < 45, f"replay too slow: {elapsed:.1f}s"

print(f"replay {elapsed:.1f}s | delta nwc {b['net_working_capital_cost'] - a['net_working_capital_cost']:,.0f}"
      f" | health {a['health_score']} vs {b['health_score']}"
      f" | shortfall {a['shortfall_days']} vs {b['shortfall_days']}")
```

## 3. The five drills

Each one takes under two minutes. Run each at least once before H+19, and the first two again
right after the freeze.

### Drill 1 — engine absent
```bash
mv engine engine_off
curl -s localhost:8000/api/health
curl -s -X POST localhost:8000/api/decide -H 'content-type: application/json' -d '{}' | head -c 120
mv engine_off engine
```
Expected: API boots, `/decide` returns the fixture. **This is why the gateway exists.**

### Drill 2 — explainer absent
```bash
mv explainer explainer_off
curl -s localhost:8000/api/health
curl -s "localhost:8000/api/decisions?policy=AGENT&limit=1" | python -c "import json,sys; print(json.load(sys.stdin)[0]['explanation'])"
mv explainer_off explainer
```
Expected: boots with a warning in the log, decisions serve with `explanation: null`.

### Drill 3 — database restart
```bash
docker compose restart db
sleep 3
curl -s "localhost:8000/api/state?policy=AGENT" | head -c 80
```
Expected: recovers. If it does not, `pool_pre_ping=True` is missing from `api/db.py`.

### Drill 4 — socket churn
Open the dashboard, hard-refresh twenty times, then fire a chaos preset.
Expected: no exception in the API log, no leaked connections, snapshot on each reconnect.

### Drill 5 — determinism
```bash
H() { docker compose exec -T db psql -U helm -d helm -tA -c \
  "select md5(string_agg(id||amount::text,',' order by id)) from invoices where policy='AGENT';"; }
curl -s -X POST localhost:8000/api/sim/reset -H 'content-type: application/json' \
  -d '{"seed":42,"start_date":"2026-03-01"}' >/dev/null; A=$(H)
curl -s -X POST localhost:8000/api/sim/reset -H 'content-type: application/json' \
  -d '{"seed":42,"start_date":"2026-03-01"}' >/dev/null; B=$(H)
[ "$A" = "$B" ] && echo "deterministic" || echo "SEED LEAK"
```

Then the stronger version: run the full replay twice and compare `ComparisonMetrics` to the
rupee. Identical or the RNG is leaking somewhere in the sim loop.

## 4. Invariants to assert in the replay

Cheap, and each one catches a real class of bug:

```python
# cash ledger reconciles
sum(delta) over policy == latest balance for that policy

# no invoice paid twice
count(invoices where status='PAID') == count(distinct ref_id in ledger where reason='INVOICE_PAYMENT')

# facility never over-drawn
every facility: drawn <= limit_amount

# no orphan actions
every action.target_id exists in invoices for that policy

# decisions cover every open invoice
len(decision.actions) == count(open invoices at that sim_day for that policy)

# every action has a rejected alternative     (PS requirement 7)
all(len(a.rejected_alternatives) >= 1 for a in decision.actions)

# CASH funding implies no facility
all(a.facility_id is None for a in decision.actions if a.funding_source == 'CASH')
```

The last two are contract requirements, not internal hygiene. If they fail, the failure is
Shyam's to fix — say it out loud with the field name; do not patch it in `api/`.

## 5. The checkpoint gates

### I1 — H+4
- [ ] `docker compose ps` shows db healthy
- [ ] `uvicorn api.main:app` boots clean
- [ ] `scripts/smoke.sh` passes on the fixture stubs
- [ ] `.gitignore` on `main` before anyone's first code commit
- [ ] Person C's Vite app can fetch from the API (CORS)

### I2 — H+8
- [ ] `/state`, `/decisions`, `/events` read real Postgres data
- [ ] `scripts/validate_shapes.py` passes
- [ ] Person C runs with `USE_MOCK=false` and the dashboard still renders
- [ ] Seed data loaded, three planted situations verified by query

### I3 — H+12, the critical one
- [ ] `POST /sim/reset` then `POST /sim/step {"days":1}` produces a persisted decision
- [ ] That decision came from the real engine (`solver.method` is not the fixture's value)
- [ ] It has an explanation attached, or `null` with a logged reason
- [ ] It appears on Person C's dashboard as an ActionCard with a real supplier name and a
      populated WhyNotPanel
- [ ] Drills 1 and 2 pass

### I4 — H+16
- [ ] `scripts/replay_check.py` passes
- [ ] All four chaos presets fire cleanly
- [ ] Preset #1 produces a non-empty `diff_from_previous.flipped`
- [ ] `metrics` frames arrive on the socket every simulated day
- [ ] Drills 3, 4 and 5 pass

### Freeze — H+19
- [ ] Everything above, re-run once
- [ ] `scripts/reset.sh` succeeds three times in a row
- [ ] Full replay run three times with identical metrics
- [ ] Every row in `12-API-CONTRACT-CHECKLIST.md` §6 ticked

## 6. What to do when a gate fails

1. **Shape failure** → your bug if it is in a serializer; Shyam's if the engine emitted it.
   Check which side of the gateway the bad field came from before saying anything.
2. **Agent does not beat the baseline** → seed data, not logic. Go back to B2 and retune with
   Shyam. Do not adjust the health score formula; it is in the contract.
3. **Replay too slow** → in order: world constants recomputed per tick, missing indexes,
   calling the engine on immaterial days.
4. **Nondeterminism** → grep for `random.` and `np.random.` outside `api/services/rng.py`.
   There will be exactly one, and it will be in the sim loop.
5. **Crash mid-replay** → the per-day transaction boundary is doing its job. Read the last
   `log` frame before the failure; it names the step.
