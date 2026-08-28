# Phase B8 — Hardening, Replay and Demo Support

**Window:** H+16 → H+19, then bugs only
**Ends at:** feature freeze

---

## 1. Goal

Make the backend boring. Streaming replay, reliable reset, error envelope everywhere,
performance inside budget, and a `reset.sh` you can run in front of a judge without thinking.

Nothing new gets built after H+19. Everything in this phase exists so that hours 19–24 are
spent rehearsing rather than debugging.

## 2. Files

```
api/routers/sim.py            # /sim/play streaming, /sim/pause
api/services/sim_runner.py    # the background replay task
scripts/reset.sh              # one command, reliable
```

## 3. Streaming replay — `POST /sim/play`

```
body: {"days": 90, "speed_ms": 300}
-> 202 Accepted immediately
-> background task advances one day every speed_ms, broadcasting as it goes
-> POST /sim/pause sets running=false; the task notices and stops
```

Implementation notes:

- Use a FastAPI `BackgroundTask` or a plain `asyncio.create_task`. **Never** hold the request
  open — 90 days at 300ms is 27 seconds and a hung request during a demo looks like a crash.
- Guard with the `sim_state.running` flag. A second `/sim/play` while running returns `409`
  in the error envelope, per section 10.
- Each simulated day opens its own DB session and its own transaction. A failure on day 43
  must not roll back days 1–42.
- Wrap the whole loop body in `try/except`: log the failure, broadcast a `log` frame at `warn`,
  set `running = false`, and stop. **A replay that dies silently is worse than one that stops
  loudly.**
- `speed_ms` is a floor, not a guarantee. If a day takes 400ms of real work at `speed_ms: 300`,
  do not try to catch up. Steady is better than accurate here.

If this route is behind schedule, it is scope cut #1 in `02-PHASE-PLAN.md`: Person C calls
`/sim/step` in a loop from the frontend and nobody can tell the difference.

## 4. `scripts/reset.sh`

You will run this before every rehearsal and possibly in front of a judge. It must be one
command with no arguments to remember.

```bash
#!/usr/bin/env bash
set -euo pipefail

docker compose up -d db
until docker compose exec -T db pg_isready -U helm >/dev/null 2>&1; do sleep 0.5; done

curl -fsS -X POST localhost:8000/api/sim/reset \
  -H 'content-type: application/json' \
  -d '{"seed":42,"start_date":"2026-03-01"}'

echo
curl -fsS localhost:8000/api/sim/status
echo
```

`set -euo pipefail` so a partial failure stops loudly instead of leaving a half-reset world.
The `pg_isready` wait loop is the fix for the "reset failed once at 2am then worked" mystery.

## 5. Performance budget

| Operation | Budget | Why |
|---|---|---|
| `GET /state` | < 100 ms | called on every dashboard refresh |
| `GET /compare` | < 50 ms | cached on `sim_state`, single row read |
| `POST /decide` | < 2.5 s | engine's 2 s cap plus overhead |
| `POST /events` | < 3 s | two forecasts plus a decide; the judge is watching |
| one simulated day | < 250 ms | 90 days must replay in under 30 s |
| `POST /sim/reset` | < 3 s | run before every rehearsal |

If a simulated day is over budget, the usual culprits in order: recomputing world constants
every tick, aggregate metrics queries without the indexes, and calling the engine on days with
no material change. Fix in that order.

## 6. Hardening checklist

- [ ] **Error envelope proven on every route.** Walk the list in `12-API-CONTRACT-CHECKLIST.md`
      and force one failure each. No HTML, no bare 500, no FastAPI validation dump.
- [ ] **Engine-absent drill.** `mv engine engine_off`, boot, hit every route, `mv` back.
- [ ] **Explainer-absent drill.** Same with `explainer/`. Decisions serve with `explanation: null`.
- [ ] **DB-restart drill.** `docker compose restart db`, then hit `/state`. With
      `pool_pre_ping=True` it recovers. Without it, it does not — this drill is how you find out.
- [ ] **Socket-churn drill.** Open and hard-refresh the dashboard twenty times. No exception,
      no leaked connection, snapshot arrives on each reconnect.
- [ ] **Double-reset determinism.** Reset, hash the invoice table, reset, hash again. Equal.
- [ ] **Full replay twice.** Same seed, same final `ComparisonMetrics`, to the rupee.
- [ ] **Chaos preset sweep.** All four presets fire cleanly at `sim_day` 12 and at `sim_day` 45.
- [ ] **Idle stability.** Leave the server up for thirty minutes with a socket connected, then
      fire a preset. Still works.

## 7. Seed tuning pass with Shyam — H+16 to H+19

`FINAL.md` section 12: *"Tuning the numbers so the story lands is legitimate work, not
cheating. Do it before the freeze, not after."*

Sit together and iterate:

1. Reset, replay 90 days, read the scoreboard.
2. If the delta is small, increase the number of discount-vs-borrow invoices in the seed.
3. If the shock produces no flip, increase `RCV-0004`'s amount or move `OBL-001` closer to the
   shock date until `diff_from_previous.flipped` is non-empty and readable.
4. If the baseline never misses payroll, tighten the opening cash or enlarge the payroll.
5. Re-freeze `seed_data.json` when it lands.

Stop when: the agent beats the baseline visibly on all three headline numbers, and preset #1
flips at least two decisions. **Then stop touching it.**

## 8. Freeze checklist — H+19

- [ ] `main` tagged
- [ ] `scripts/reset.sh` run successfully three times in a row
- [ ] Full replay run three times, identical metrics each time
- [ ] All four chaos presets rehearsed
- [ ] `.env.example` matches what is actually needed to boot from a clean clone
- [ ] Every route in `12-API-CONTRACT-CHECKLIST.md` ticked
- [ ] `docs/backend/15-RUNBOOK.md` reviewed and accurate

After the freeze: **bugs only.** No new routes, no new fields, no refactors, no "quick
improvements". Person B's job for the last five hours is to keep a terminal ready and be able
to restart anything in under fifteen seconds.

## 9. Verify

```bash
./scripts/reset.sh

curl -s -X POST localhost:8000/api/sim/play -H 'content-type: application/json' \
  -d '{"days":90,"speed_ms":100}' -o /dev/null -w '%{http_code}\n'    # 202
curl -s -X POST localhost:8000/api/sim/play -H 'content-type: application/json' \
  -d '{"days":90,"speed_ms":100}' | grep -q CONFLICT && echo "409 envelope ok"

sleep 12 && curl -s localhost:8000/api/sim/status
curl -s -X POST localhost:8000/api/sim/pause

# drills
mv engine engine_off; curl -s localhost:8000/api/health; mv engine_off engine
mv explainer explainer_off; curl -s localhost:8000/api/health; mv explainer_off explainer
docker compose restart db && sleep 3 && curl -s "localhost:8000/api/state?policy=AGENT" | head -c 80
```
