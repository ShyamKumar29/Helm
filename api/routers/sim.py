# api/routers/sim.py — B0 stubbed step/play/pause/status/execute: shape-correct, no DB.
# B2 made /sim/reset real (the seed trigger, not the day loop). B5 makes /sim/step,
# /sim/status and /sim/pause real, driving api/services/sim_loop.py.
#
# /sim/play stays a 202 stub: real background streaming needs the WebSocket hub, which is
# B6/B8 (docs/backend/12-API-CONTRACT-CHECKLIST.md marks it "Real in B8"; 02-PHASE-PLAN.md
# lists streaming as the first thing to cut if behind). /execute/{id} is likewise left as the
# B0 stub — 02-PHASE-PLAN.md calls it a cuttable convenience route ("the sim loop already
# executes scheduled actions") and B5's own build steps never mention it.
import logging

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api import config
from api.db import get_session
from api.errors import HelmError
from api.models import SimState
from api.seed.seed import seed_world
from api.services import sim_loop
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
def sim_play(body: SimPlayBody, response: Response):
    # Real implementation streams over the "/api/stream" WebSocket (B6/B8).
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
