# api/services/sim_runner.py — B8. The background task behind `POST /sim/play`
# (docs/backend/11-PHASE-B8-hardening-and-demo.md section 3).
#
# This is NOT a second simulation loop. It calls api.services.sim_loop.advance_one_day()
# once per simulated day — the exact same function `POST /sim/step` calls — and broadcasts
# what comes back over the existing api.services.ws.hub. Nothing about the day loop itself
# changes; this module only adds the "run N of them, one every speed_ms, until paused or
# done" behaviour that a live demo replay needs.
#
# Rules straight from the phase doc:
#   - never hold an HTTP request open: the router starts this as a fire-and-forget task and
#     returns 202 immediately (api/routers/sim.py)
#   - one DB session, one transaction, per simulated day: a failure on day 43 must not roll
#     back days 1-42 (sim_loop.advance_one_day already opens/commits per call; we just give
#     it a fresh session each iteration)
#   - `sim_state.running` is the pause flag: POST /sim/pause flips it in the DB, and this
#     loop notices at the top of its next iteration and stops — no separate signalling
#     mechanism
#   - the whole loop body is wrapped in try/except: log, broadcast a "log" frame at warn,
#     set running=false, stop. A replay that dies silently is worse than one that stops
#     loudly.
#   - `speed_ms` is a floor, not a guarantee: we sleep *after* the day's work, and never try
#     to catch up if a day ran long.
from __future__ import annotations

import asyncio
import logging

from api.db import SessionLocal
from api.models import SimState
from api.services import sim_loop
from api.services.ws import hub

log = logging.getLogger(__name__)

# Strong references to in-flight play tasks. asyncio only holds a weak reference to a task
# via the event loop, and a task with nothing else referencing it can be garbage-collected
# mid-run — this set is the fix, per the asyncio docs' own warning on `create_task`.
_TASKS: set[asyncio.Task] = set()


def _set_running(running: bool) -> None:
    db = SessionLocal()
    try:
        sim = db.get(SimState, 1)
        if sim is not None:
            sim.running = running
            db.commit()
    finally:
        db.close()


def _is_running() -> bool:
    db = SessionLocal()
    try:
        sim = db.get(SimState, 1)
        return sim is not None and bool(sim.running)
    finally:
        db.close()


async def _run(days: int, speed_ms: int) -> None:
    sleep_s = max(speed_ms, 0) / 1000.0
    last_sim_day = 0
    completed = 0

    try:
        for _ in range(days):
            if not _is_running():
                # Paused (POST /sim/pause) or the world was reset out from under us —
                # stop quietly, this is not a failure.
                break

            db = SessionLocal()
            try:
                result = sim_loop.advance_one_day(db)
            finally:
                db.close()

            completed += 1
            last_sim_day = result.sim_day

            await hub.send(
                "sim",
                result.sim_day,
                {"sim_day": result.sim_day, "running": True},
            )
            for event in result.events:
                await hub.send("event", result.sim_day, event)
            for decision in result.decisions:
                await hub.send("decision", result.sim_day, decision)
            try:
                await hub.send("metrics", result.sim_day, result.metrics)
            except Exception:
                log.exception(
                    "sim/play day %s: metrics broadcast failed", result.sim_day
                )
            await hub.send(
                "log",
                result.sim_day,
                {
                    "level": "info",
                    "text": (
                        f"sim/play day {result.sim_day} advanced - "
                        f"{len(result.events)} event(s), "
                        f"{len(result.decisions)} decision(s)"
                    ),
                },
            )

            await asyncio.sleep(sleep_s)
        else:
            # Loop ran to completion (never hit `break`) — the replay finished on its own,
            # not via pause. Stop cleanly rather than leaving `running=True` forever.
            _set_running(False)
            await hub.send(
                "log",
                last_sim_day,
                {"level": "info", "text": f"sim/play finished after {completed} day(s)"},
            )
    except Exception:
        log.exception("sim/play failed after %d/%d day(s)", completed, days)
        _set_running(False)
        try:
            await hub.send(
                "log",
                last_sim_day,
                {
                    "level": "warn",
                    "text": (
                        f"sim/play failed after {completed} day(s), stopping - see server log"
                    ),
                },
            )
        except Exception:
            log.exception("sim/play: could not even broadcast the failure log frame")


def start(days: int, speed_ms: int) -> asyncio.Task:
    """Fire-and-forget a replay of up to `days` simulated days. Caller (the router) has
    already set `sim_state.running = True` and committed before calling this, so the very
    first iteration's `_is_running()` check sees it."""
    task = asyncio.create_task(_run(days, speed_ms))
    _TASKS.add(task)
    task.add_done_callback(_TASKS.discard)
    return task
