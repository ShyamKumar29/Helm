#!/usr/bin/env python
"""scripts/verify_b8_sim_play.py — B8 checks that need no DB and no pytest, matching the
project's own testing philosophy (docs/backend/14-TESTING-AND-VERIFICATION.md: "Not a test
suite. A set of gates."). Run with the repo's venv Python from the repo root:

    python scripts/verify_b8_sim_play.py

Covers what /sim/play can prove without Postgres: the app still boots with engine/ and
explainer/ absent (the B0/B8 "done" criteria), and the two validation branches that are
checked *before* any DB access (days < 1, speed_ms < 0) return the frozen error envelope.

Everything else in docs/backend/11-PHASE-B8-hardening-and-demo.md section 9 — the 202/409
sequence, the background replay itself, the hardening drills, the freeze checklist — needs a
live Postgres and is NOT exercised here. No Postgres/docker is available in this environment
(same limitation scripts/verify_b7_metrics.py already recorded for B7). See the B8 handoff
report for the exact list of what remains to be run once a DB is available.
"""

from fastapi.testclient import TestClient

import api.main as app_module

failures = []


def check(name, condition):
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        failures.append(name)


# --------------------------------------------------------------------------------------
# The app boots with engine/ and explainer/ absent, and every B8-touched route is mounted.
# --------------------------------------------------------------------------------------
schema = app_module.app.openapi()
paths = schema["paths"]

check("POST /api/sim/play is mounted", "post" in paths.get("/api/sim/play", {}))
check("POST /api/sim/pause is mounted", "post" in paths.get("/api/sim/pause", {}))
check("GET /api/health is mounted (engine/explainer absent)", "get" in paths.get("/api/health", {}))

client = TestClient(app_module.app)

# --------------------------------------------------------------------------------------
# Validation happens before any DB access — these two must return fast (no hang, no 500)
# even with Postgres completely unreachable, because they raise before the handler's first
# db.get(SimState, 1).
# --------------------------------------------------------------------------------------
r = client.post("/api/sim/play", json={"days": 0, "speed_ms": 100})
check("days < 1 -> 400 VALIDATION envelope", r.status_code == 400)
check(
    "days < 1 envelope shape is frozen {error:{code,message,detail}}",
    set(r.json().keys()) == {"error"} and set(r.json()["error"].keys()) == {"code", "message", "detail"},
)
check("days < 1 error code is VALIDATION", r.json()["error"]["code"] == "VALIDATION")

r2 = client.post("/api/sim/play", json={"days": 5, "speed_ms": -1})
check("speed_ms < 0 -> 400 VALIDATION envelope", r2.status_code == 400)
check("speed_ms < 0 error code is VALIDATION", r2.json()["error"]["code"] == "VALIDATION")

# --------------------------------------------------------------------------------------
# sim_runner shape — the background task module never imports a router (services stay one
# layer below routers, 00-BACKEND-OVERVIEW.md section 3) and exposes exactly one public
# entry point for the router to call.
# --------------------------------------------------------------------------------------
from api.services import sim_runner  # noqa: E402

check("sim_runner exposes start()", callable(getattr(sim_runner, "start", None)))
check(
    "sim_runner keeps a strong reference set for in-flight tasks (no GC'd replay)",
    isinstance(sim_runner._TASKS, set),
)

print(f"  ---- {len(failures)} failed")
print(
    "  NOTE: 202/409 sequencing, background broadcasts, and the phase doc's drills all need "
    "Postgres and are not covered by this script."
)
if failures:
    raise SystemExit(1)
