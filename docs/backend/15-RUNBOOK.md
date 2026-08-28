# 15 — Runbook

For hour 20, when something is on fire and you have four minutes.

---

## 1. Start everything

```bash
docker compose up -d db
until docker compose exec -T db pg_isready -U helm >/dev/null 2>&1; do sleep 0.5; done
uvicorn api.main:app --reload --port 8000
```

Frontend is Person C's: `cd web && npm run dev` on `:5173`.

## 2. Reset the world

```bash
./scripts/reset.sh
```

Run this before every rehearsal and before the real demo. If it fails, run the three steps
inside it by hand — the failure is almost always Postgres not being ready yet.

## 3. Nuclear reset

When the database is in a state you do not understand:

```bash
docker compose down
rm -rf postgres-data/
docker compose up -d db
until docker compose exec -T db pg_isready -U helm >/dev/null 2>&1; do sleep 0.5; done
python -c "from api.db import reset_schema; reset_schema()"
./scripts/reset.sh
```

Takes about 40 seconds. Cheaper than ten minutes of diagnosis at hour 21.

> **Warning:** `rm -rf postgres-data/` permanently deletes all simulation data in the local
> database. Everything is regenerated from the seed, so nothing unrecoverable is lost — but
> confirm you are in the repo root before running it.

## 4. Failure playbook

### API will not boot

```
ImportError / ModuleNotFoundError on contracts.*
```
Running from the wrong directory. `uvicorn` must be started from the repo root so `contracts/`
is importable. Not from inside `api/`.

```
sqlalchemy.exc.OperationalError: could not connect
```
Postgres is not up or not ready. `docker compose ps`, then `docker compose up -d db`, then
wait for `pg_isready`.

```
explainer not mounted: ...
```
**This is a warning, not an error.** The API is fine. Person C's router is absent or broken.
Tell them; keep working.

### Route returns 500

Check the log for the traceback. The unhandled-exception handler turns everything into
`{"error":{"code":"INTERNAL",...}}`, so the frontend does not crash — but the traceback is in
your terminal, and it names the line.

Most common at hour 15: a `Decimal` reaching `json.dumps` because a serializer was bypassed.
Fix in `serializers.py`, not at the call site.

### Frontend shows nothing

In order:
1. `curl localhost:8000/api/health` — is the API up?
2. Browser console — CORS error? `config.CORS_ORIGINS` must contain `http://localhost:5173`.
3. Is Person C on `USE_MOCK=true`? Then they are not talking to you at all.
4. `curl "localhost:8000/api/state?policy=AGENT"` — is the shape right?

### Decisions stopped appearing

1. `GET /api/sim/status` — is `sim_day` advancing?
2. `GET /api/decisions?policy=AGENT&limit=1` — is anything persisted?
3. Check the `log` frames: is materiality scoring below threshold every day? Lower
   `MATERIALITY_THRESHOLD` temporarily to confirm, then put it back — the threshold is a
   demo talking point, not a bug.
4. Is the engine degrading? Grep the log for `engine.decide raised` or `exceeded ... budget`.

### The shock does nothing visible

Not a backend bug. Check in order:
1. Did the event persist? `GET /api/events?limit=1`
2. What was `materiality_score`? Below 0.15 means the seed is not dramatic enough.
3. Is `diff_from_previous.flipped` empty on the resulting decision? That is a seed-data
   problem (phase B2) or an engine diff problem (Shyam) — check which by looking at whether
   any action actually changed between the two decisions.

### Replay is slow

1. Are world constants being recomputed every tick? Cache them on `sim_state`.
2. `\di` in psql — are all four indexes present?
3. Is the engine being called on every day regardless of materiality?
4. Last resort: ask Shyam out loud to drop `n_paths` to 500. Nobody can see the difference.

### Numbers look wrong

The cash ledger is the answer to every "where did the money go" question:

```sql
select reason, count(*), sum(delta)
from cash_ledger where policy='AGENT' group by reason order by 3;

select sim_day, date, reason, delta, balance, ref_id
from cash_ledger where policy='AGENT' order by id desc limit 30;
```

Two minutes instead of forty. This is the entire reason the ledger is append-only.

## 5. Useful queries

```bash
psql() { docker compose exec -T db psql -U helm -d helm -c "$1"; }

psql "select * from sim_state;"
psql "select policy, status, count(*) from invoices group by 1,2 order by 1,2;"
psql "select policy, count(*) from decisions group by 1;"
psql "select type, count(*) from events group by 1 order by 2 desc;"
psql "select event_id, type, materiality_score, triggered_reoptimization
      from events order by sim_day desc limit 10;"
psql "select policy, id, drawn, limit_amount from facilities order by 1,2;"
psql "select policy, min(balance), max(balance) from cash_ledger group by 1;"
psql "select count(*) from cash_ledger where policy='AGENT' and balance < 0;"
```

## 6. Environment variables that change behaviour

| Var | Default | Effect |
|---|---|---|
| `MATERIALITY_THRESHOLD` | 0.15 | lower means re-optimise more often; a demo talking point |
| `SOLVER_TIMEOUT_MS` | 2000 | the engine's own cap; the gateway adds 1500 ms of margin |
| `SIM_SEED` | 42 | changes the whole world; **do not change after the seed is tuned** |
| `SIM_START_DATE` | 2026-03-01 | shifts every date, including the planted payroll |
| `EXPLAINER_MODE` | template | `template` or `llm`; template needs no API key |
| `CORS_ORIGINS` | localhost:5173 | add the LAN IP if demoing from another machine |
| `HORIZON_DAYS` | 90 | forecast horizon |

**Do not change `SIM_SEED` or `SIM_START_DATE` after H+16.** Every planted situation, every
hardcoded frontend ID and every rehearsed demo beat depends on them.

## 7. During the demo — Person B's job

`FINAL.md` section 16: *"Person B keeps a terminal ready in case something needs a restart."*

Have these ready before the judges arrive:

```
Terminal 1:  uvicorn api.main:app --port 8000        (visible log)
Terminal 2:  ./scripts/reset.sh                      (typed, not run)
Terminal 3:  docker compose logs -f db               (idle)
```

If the API dies mid-demo: Ctrl-C, up-arrow, Enter. Under five seconds, and the frontend
reconnects the socket on its own.

If the world gets into a strange state between rehearsals: Terminal 2, Enter. Under three
seconds.

**Do not debug during the demo.** Restart, let Person C keep talking, diagnose afterwards.

## 8. Ten-minute pre-demo checklist

- [ ] `docker compose ps` — db healthy
- [ ] `./scripts/reset.sh` — clean, twice
- [ ] `scripts/smoke.sh` — all green
- [ ] `GET /api/compare` — agent visibly ahead
- [ ] All four chaos presets fired once and reset afterwards
- [ ] WebSocket connected from the actual demo browser tab
- [ ] Laptop on power, wifi off if the demo is fully local
- [ ] Terminals 1–3 arranged and reset typed but not run
