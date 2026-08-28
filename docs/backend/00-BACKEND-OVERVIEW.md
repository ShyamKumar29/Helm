# 00 — Backend Overview (Person B)

**Owner:** Person B
**Scope of this folder:** everything Person B builds, in the order it gets built.
**Authority:** `FINAL.md` is the source of truth. These files are the working plan derived from it.
If a phase file and `FINAL.md` disagree, `FINAL.md` wins and the phase file is the defect.

---

## 1. What the backend is

`api/` is the only component that:

- talks to Postgres
- owns the simulation clock (`sim_day`)
- decides *whether* to re-optimise (materiality)
- calls `engine.decide()` and persists what comes back
- runs the BASELINE agent
- computes `ComparisonMetrics`, `health_score`, `savings_per_day`
- broadcasts everything on the WebSocket

It is the hub. The engine is a pure function it calls; the explainer is a router it mounts;
the frontend is a client it feeds. **Both of those are optional at boot time.** The API must
start, serve, and demo with `engine/` and `explainer/` entirely absent.

## 2. What the backend is NOT

It never:

- computes a cash forecast, a `deployable_cash`, a `net_value`, a `reason_code`, or a
  `rejected_alternative`. Those belong to the engine.
- writes English prose. That belongs to the explainer.
- renders anything. That belongs to `web/`.
- edits `engine/`, `explainer/`, or `web/`. Ever. Not once. Not "just to fix a typo".

If a number the backend needs is missing or wrong, the fix is a sentence spoken out loud to
Shyam or Person C — not a commit.

## 3. Internal architecture of `api/`

Four layers, strictly one-directional. Nothing lower imports from anything higher.

```
routers/     HTTP surface. Thin. Parse, call a service, shape the response.
   |
services/    All logic. Sim loop, state builder, materiality, metrics, executor, ws hub.
   |
baseline/    The static-rules agent. Reads state, emits decisions in the same shape.
   |
models.py    SQLAlchemy ORM + db.py session factory. No logic.
```

Rules that hold this shape:

- **A router never imports another router.** Shared logic goes down into `services/`.
- **A service never imports a router.** If it needs a value from the request, it takes it
  as an argument.
- **`baseline/` imports `models` and `services/` helpers, never a router.**
- **`main.py` imports every router and nothing else.** Written at H+1, frozen forever.

Why this matters at 3am: when a route misbehaves you look in exactly one file, and when the
sim loop misbehaves you look in exactly one other. No circular import will ever appear.

## 4. The two hard boundaries

### 4.1 The engine boundary

One file — `api/services/engine_gateway.py` — is the **only** place in `api/` that imports
from `engine/`. Every other module calls the gateway.

```python
# api/services/engine_gateway.py  — the single import site
import json, pathlib, logging

log = logging.getLogger(__name__)
_FIXTURES = pathlib.Path("contracts/fixtures")

try:
    from engine.decide import decide as _decide, forecast as _forecast
    ENGINE_AVAILABLE = True
except Exception as e:                       # engine absent or broken
    log.warning("engine not importable, using fixtures: %s", e)
    ENGINE_AVAILABLE = False

def decide(state, weights=None, previous=None, trigger=None):
    if not ENGINE_AVAILABLE:
        return json.loads((_FIXTURES / "decision.sample.json").read_text(encoding="utf-8"))
    return _decide(state, weights=weights, previous=previous, trigger=trigger)

def forecast(state, horizon_days=90):
    if not ENGINE_AVAILABLE:
        return json.loads((_FIXTURES / "forecast.sample.json").read_text(encoding="utf-8"))
    return _forecast(state, horizon_days=horizon_days)
```

Consequences, all of them good:

- The API boots at H+1 when `engine/` is an empty folder.
- Swapping fixture to real engine is a zero-diff event elsewhere in the codebase.
- When the engine throws at hour 19, one `try/except` in the gateway degrades the whole
  system to last-known-good instead of taking the demo down.

**The gateway also enforces the timeout and catches engine exceptions.** Detail in phase B4.

### 4.2 The explainer boundary

`api/main.py` mounts `explainer.router` inside a `try/except`, exactly as written in
`FINAL.md` section 6. That is the entire coupling. `api/` never imports `explainer` anywhere
else, never calls a function in it directly, and never reads its files.

When the API wants an explanation attached to a decision it just persisted, it makes an
**internal HTTP call to its own `/api/explain/{decision_id}`**, wrapped in a try/except with
a 3-second timeout. If it fails, `decision.explanation` stays `null` and the frontend renders
the decision without prose. Nothing breaks.

## 5. Ordering guarantee

The nine phases are ordered so **the API boots and every route returns a valid contract shape
at the end of every phase.** There is no phase where the backend is legitimately broken.

Phase B0 already gives Person C a server that answers every route in `FINAL.md` section 10
with fixture data. Everything after B0 replaces fake internals with real ones, one route at a
time, without changing a single response shape.

That is the whole strategy: **shape first, truth second.**

## 6. Read order

1. `01-OWNERSHIP-AND-CONFLICT-RULES.md` — read before writing any code
2. `02-PHASE-PLAN.md` — the map
3. `03-PHASE-B0-bootstrap.md` through `11-PHASE-B8-hardening-and-demo.md` — in order
4. `12-API-CONTRACT-CHECKLIST.md` — keep open in a tab the whole night
5. `13-SEED-DATA-SPEC.md` — read fully before phase B2
6. `14-TESTING-AND-VERIFICATION.md` — the gates
7. `15-RUNBOOK.md` — when something is on fire

## 7. Definition of "done" for the backend as a whole

All of these true at H+19:

- [ ] `docker compose up -d db` then `uvicorn api.main:app` boots clean, no warnings that matter
- [ ] `POST /api/sim/reset` rebuilds an identical world, verified twice by hash
- [ ] Every route in section 10 returns a shape that validates against `contracts/schemas.py`
- [ ] `POST /api/sim/play {"days": 90}` completes a full replay without an unhandled exception
- [ ] The scoreboard shows AGENT beating BASELINE on `net_working_capital_cost`, `shortfall_days` and `obligations_missed`
- [ ] Firing chaos preset #1 produces a decision whose `diff_from_previous.flipped` is non-empty
- [ ] The WebSocket emits `log` frames for both "re-optimising" and "no change needed" cases
- [ ] Killing `engine/` (rename the folder) leaves the API booting and serving fixtures
- [ ] Killing `explainer/` (rename the folder) leaves the API booting and serving decisions with `explanation: null`
