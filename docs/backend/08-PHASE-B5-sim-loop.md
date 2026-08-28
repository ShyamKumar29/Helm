# Phase B5 — The Simulation Loop

**Window:** H+9 → H+12
**This phase carries checkpoint I3: one invoice, end to end.**

---

## 1. Goal

The eight-step day loop from `FINAL.md` section 13, with each step a separate, separately
testable function, plus the `/sim/*` routes that drive it. Cash moves only through the ledger.

## 2. Files

```
api/services/clock.py       # sim_day / as_of arithmetic, the only date math in api/
api/services/sim_loop.py    # the eight steps, one function each
api/services/executor.py    # applies actions to the world, writes the ledger
api/services/rng.py         # seeded, reproducible sampling
api/routers/sim.py          # /sim/reset, /sim/step, /sim/status, /sim/pause
```

## 3. The loop, step by step

`sim_loop.advance_one_day(session)` calls eight functions in order. Each returns a list of
`Event` dicts it generated, and the caller accumulates them.

```python
def advance_one_day(session) -> DayResult:
    events = []
    sim = step_1_advance_clock(session);            events += sim.events
    events += step_2_roll_receivables(session, sim)
    events += step_3_apply_obligations(session, sim)
    events += step_4_execute_scheduled_actions(session, sim)
    material = step_5_score_materiality(session, sim, events)
    decision = step_6_maybe_reoptimize(session, sim, events, material)
    baseline = step_7_run_baseline(session, sim)
    metrics  = step_8_recompute_metrics(session, sim)
    return DayResult(sim_day=sim.sim_day, events=events,
                     decisions=[d for d in (decision, baseline) if d], metrics=metrics)
```

### Step 1 — advance the clock

Increment `sim_state.sim_day`, recompute `as_of = start_date + sim_day`. Emit a
`DAY_ADVANCED` event with payload `{"new_sim_day", "new_date"}`. That payload shape is frozen
in section 8.6 — match it exactly.

### Step 2 — roll receivable arrivals

For each `OPEN` receivable, decide whether it collects today using a **seeded, reproducible**
draw:

```python
# api/services/rng.py
import hashlib, numpy as np

def gen(seed: int, *parts) -> np.random.Generator:
    key = ":".join(str(p) for p in parts).encode()
    h = int.from_bytes(hashlib.blake2b(key, digest_size=8).digest(), "big")
    return np.random.default_rng((seed ^ h) % (2**63))
```

Call it as `gen(sim.seed, receivable_id)` — **not** including `sim_day`, so a receivable's
realised delay is decided once and stays decided. Sample the delay per `FINAL.md` section 11.4
(bootstrap from `historical_delays` when there are 5+ samples, otherwise the truncated normal,
always with the `on_time_probability` mixture). Cache the realised arrival date on the row the
first time it is drawn.

When `as_of == realised_arrival`: mark `COLLECTED`, set `actual_date`, append a `cash_ledger`
row (`delta = +amount`, reason `"RECEIVABLE_COLLECTED"`, `ref_id = receivable.id`) **for both
policies**, and emit `RECEIVABLE_COLLECTED` with `{"receivable_id", "amount", "days_late"}`.

Receivables are the outside world — they collect identically in both policies. Only *decisions*
differ between AGENT and BASELINE.

### Step 3 — apply due obligations

For each unsettled obligation with `due_date == as_of`, for each policy: append a negative
ledger row (reason `"OBLIGATION"`, `ref_id = obligation.id`). Set `settled_on` once — the
obligation table is shared, so track per-policy settlement in the ledger, not on the row.

**If the resulting balance goes negative, do not block it.** Let it go negative and record it.
A negative balance in the BASELINE world on payroll day *is the demo*: it becomes
`shortfall_days` and `obligations_missed` on the scoreboard. Suppressing it destroys the story.

### Step 4 — execute scheduled actions

Read the newest decision per policy. For every action whose `execute_on == as_of` and whose
`status == "PROPOSED"`:

| action | effect |
|---|---|
| `PAY_NOW`, `PAY_AT_MATURITY` | ledger `-amount`; invoice `PAID`, `paid_on`, `paid_amount`, `funding_source = "CASH"` |
| `PAY_EARLY_DISCOUNT` | ledger `-(amount × (1 - discount_pct/100))`; invoice `PAID`; record discount captured |
| `DELAY` | nothing today; the action's `execute_on` is already the delayed date, so it pays then with the penalty added |
| `FINANCE_BANK` | facility `drawn += amount`; ledger `-amount` **and** `+amount` (draw in, payment out) or net zero with two rows; invoice `FINANCED` |
| `FINANCE_SUPPLIER` | facility `drawn += amount`; invoice `FINANCED`; no cash movement today |
| `HOLD` | nothing |

Mark the action `EXECUTED`. If cash is insufficient for a `PAY_*` action, mark it `ESCALATED`,
emit a log frame, and leave the invoice open — **never silently skip it.**

Emit `INVOICE_PAID` with the frozen payload
`{"invoice_id", "amount", "funding_source", "discount_captured", "penalty_paid"}`.

**Two ledger rows, never one, for a financed payment.** It makes the ledger readable when you
are reconciling at hour 20.

### Step 5 — materiality

Detail is in phase B6. For B5, a placeholder that returns `1.0` on any non-`DAY_ADVANCED`
event and `0.0` otherwise is enough to keep the loop moving.

### Step 6 — maybe re-optimise (AGENT only)

If `materiality >= MATERIALITY_THRESHOLD` **or** this is the scheduled daily run: build state,
call the gateway, validate, stamp `decision_id`/`run_at`/`sim_day`/`policy = "AGENT"`, persist,
attach the explanation, broadcast.

Otherwise: persist nothing, and emit a `log` frame saying so. That declined line is worth real
points — `FINAL.md` section 13 is explicit about it.

### Step 7 — run the baseline (BASELINE only)

Phase B7. Stub returning `None` for now.

### Step 8 — recompute metrics

Phase B7. Stub returning the fixture for now.

## 4. Cash ledger discipline

The single most important rule in this phase.

```python
# api/services/ledger.py
def post(session, policy: str, sim_day: int, date, delta: Decimal, reason: str, ref_id: str | None):
    prev = latest_balance(session, policy)          # SELECT ... ORDER BY id DESC LIMIT 1
    row = CashLedger(sim_day=sim_day, date=date, policy=policy,
                     delta=delta, balance=prev + delta, reason=reason, ref_id=ref_id)
    session.add(row)
    return row.balance
```

**Every rupee that moves goes through `post()`.** There is no other way to change cash. No
`UPDATE`, no in-place mutation, no "just this once".

Reasons are a small closed vocabulary — `OPENING_BALANCE`, `RECEIVABLE_COLLECTED`,
`OBLIGATION`, `INVOICE_PAYMENT`, `FACILITY_DRAW`, `FACILITY_REPAY`, `INTEREST`, `PENALTY` —
so that `SELECT reason, sum(delta) FROM cash_ledger WHERE policy='AGENT' GROUP BY reason`
answers "where did the money go" in one query. You will run that query at hour 20.

## 5. The routes

| Route | Behaviour |
|---|---|
| `POST /sim/reset` | `reset_schema()`, seed both policies, write `sim_state` row, broadcast `sim` frame. Returns `{"sim_day": 0, "as_of": "..."}`. Must be idempotent and fast. |
| `POST /sim/step` | `advance_one_day()` × `days`. Returns `{"sim_day", "events": [...], "decisions": [...]}`. |
| `POST /sim/play` | Set `running = true`, return `202` immediately, drive the loop from a background task at `speed_ms` per day, broadcasting each day. Never hold the request open. |
| `POST /sim/pause` | Set `running = false`. Returns `{"sim_day", "paused": true}`. |
| `GET /sim/status` | `{"sim_day", "as_of", "running", "horizon_days"}` from the `sim_state` row. |

`POST /sim/play` while already running returns `409` in the error envelope, per section 10.

**One transaction per simulated day.** Commit at the end of `advance_one_day`. If a day fails
halfway, the whole day rolls back and the world stays consistent — much easier to reason about
at 3am than a half-applied day.

## 6. Checkpoint I3 — one invoice end to end

This is the gate the whole project stops for. The path:

```
POST /sim/reset
POST /sim/step {"days": 1}
  -> state built from Postgres
  -> engine.decide() called through the gateway
  -> DecisionObject validated and persisted
  -> explanation attached (or null)
  -> broadcast on the socket
  -> Person C's dashboard renders one ActionCard with a real supplier name,
     a real amount, a real reason, and a WhyNotPanel with a rejected alternative
```

Ugly is fine. If this does not work at H+12, everything else stops until it does.

## 7. Definition of done

- [ ] `POST /sim/reset` rebuilds the world in under 3 seconds, twice, identically
- [ ] `POST /sim/step {"days":1}` advances the clock and returns events
- [ ] `POST /sim/step {"days":30}` runs 30 days without an unhandled exception
- [ ] Cash only ever changes via `ledger.post()` — grep proves no other writer
- [ ] `SELECT reason, sum(delta) FROM cash_ledger GROUP BY reason` reconciles to the current balance
- [ ] A decision is persisted and retrievable via `GET /decisions`
- [ ] Insufficient-cash payments are `ESCALATED`, not skipped
- [ ] Receivable realised delays are stable across reruns with the same seed
- [ ] Checkpoint I3 demonstrated on screen with Person C and Shyam watching

## 8. Verify

```bash
curl -s -X POST localhost:8000/api/sim/reset -H 'content-type: application/json' \
  -d '{"seed":42,"start_date":"2026-03-01"}'
curl -s -X POST localhost:8000/api/sim/step -H 'content-type: application/json' -d '{"days":30}' \
  | python -c "import json,sys; r=json.load(sys.stdin); print(r['sim_day'], len(r['events']), len(r['decisions']))"

psql() { docker compose exec -T db psql -U helm -d helm -c "$1"; }
psql "select reason, count(*), sum(delta) from cash_ledger where policy='AGENT' group by reason order by 3;"
psql "select balance from cash_ledger where policy='AGENT' order by id desc limit 1;"
psql "select status, count(*) from invoices where policy='AGENT' group by status;"

# determinism: reset+step twice, balances must match
```
