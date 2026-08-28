# api/routers/sim.py — B0 stubbed step/play/pause/status/execute: shape-correct, no DB.
# B2 made /sim/reset real (the seed trigger, not the day loop). B5 makes /sim/step,
# /sim/status and /sim/pause real, driving api/services/sim_loop.py. B8 makes /sim/play
# real: a fire-and-forget background replay (api/services/sim_runner.py) that reuses
# sim_loop.advance_one_day() one day at a time and broadcasts on the existing hub
# (docs/backend/11-PHASE-B8-hardening-and-demo.md section 3).
#
# /execute/{id} is left as the B0 stub — 02-PHASE-PLAN.md calls it a cuttable convenience
# route ("the sim loop already executes scheduled actions") and neither B5's nor B8's build
# steps mention making it real.
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api import config
from api.db import get_session
from api.errors import HelmError
from api.models import SimState
from api.seed.seed import seed_world
from api.services import sim_loop, sim_runner
from api.services.ws import hub

log = logging.getLogger(__name__)

router = APIRouter(tags=["sim"])


class SimResetBody(BaseModel):
    seed: int = config.SIM_SEED
    start_date: str = config.SIM_START_DATE


class SimStepBody(BaseModel):
    days: int = 1


class SimPlayBody(BaseModel):
    days: int = config.HORIZON_DAYS
    speed_ms: int = 300


@router.post("/sim/reset")
def sim_reset(body: SimResetBody):
    summary = seed_world(seed=body.seed, start_date=body.start_date)
    return {"sim_day": summary["sim_day"], "as_of": summary["as_of"]}


@router.post("/sim/step")
async def sim_step(body: SimStepBody, db: Session = Depends(get_session)):
    if body.days < 1:
        raise HelmError("VALIDATION", "days must be >= 1", 400, {"days": body.days})

    events: list[dict] = []
    decisions: list[dict] = []
    sim_day = None
    for _ in range(body.days):
        result = sim_loop.advance_one_day(db)
        sim_day = result.sim_day
        events += result.events
        decisions += result.decisions
        # B7 (docs/backend/10-PHASE-B7-baseline-and-metrics.md section 5): the identical
        # ComparisonMetrics object step 8 just computed, broadcast on the "metrics" channel
        # after every simulated day. A broadcast failure never fails an already-committed
        # day (same bulletproofing rule api/routers/events.py's forecast broadcast follows).
        try:
            await hub.send("metrics", sim_day, result.metrics)
        except Exception:
            log.exception("sim_day %s: metrics broadcast failed", sim_day)

    return {"sim_day": sim_day, "events": events, "decisions": decisions}


@router.post("/sim/play", status_code=202)
async def sim_play(body: SimPlayBody, db: Session = Depends(get_session)):
    if body.days < 1:
        raise HelmError("VALIDATION", "days must be >= 1", 400, {"days": body.days})
    if body.speed_ms < 0:
        raise HelmError(
            "VALIDATION", "speed_ms must be >= 0", 400, {"speed_ms": body.speed_ms}
        )

    sim = db.get(SimState, 1)
    if sim is None:
        raise HelmError(
            "NOT_FOUND", "simulation not initialized - call POST /sim/reset first", 404
        )
    if sim.running:
        raise HelmError(
            "CONFLICT", "simulation already running - call POST /sim/pause first", 409
        )

    # Set before returning: this is the flag both a concurrent /sim/play (checked above)
    # and the background task's own pause check (sim_runner._is_running) key off of.
    sim.running = True
    db.commit()

    # Never hold this request open — 202 immediately, the day loop runs in the background
    # and broadcasts over WS /api/stream as it goes (section 3 of the phase doc).
    sim_runner.start(body.days, body.speed_ms)
    return {"accepted": True, "days": body.days, "speed_ms": body.speed_ms}


@router.post("/sim/pause")
def sim_pause(db: Session = Depends(get_session)):
    sim = db.get(SimState, 1)
    if sim is None:
        raise HelmError(
            "NOT_FOUND", "simulation not initialized - call POST /sim/reset first", 404
        )
    sim.running = False
    db.commit()
    return {"sim_day": sim.sim_day, "paused": True}


@router.get("/sim/status")
def sim_status(db: Session = Depends(get_session)):
    sim = db.get(SimState, 1)
    if sim is None:
        return {
            "sim_day": 0,
            "as_of": config.SIM_START_DATE,
            "running": False,
            "horizon_days": config.HORIZON_DAYS,
        }
    return {
        "sim_day": sim.sim_day,
        "as_of": sim.as_of.isoformat(),
        "running": sim.running,
        "horizon_days": sim.horizon_days,
    }


@router.post("/execute/{decision_id}")
def execute_decision(decision_id: str):
    return {"executed": 0, "escalated": 0}
