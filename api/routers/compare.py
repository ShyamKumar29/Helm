# api/routers/compare.py — B7. GET /compare, real now (docs/backend/
# 10-PHASE-B7-baseline-and-metrics.md section 5). Router stays thin: all computation lives
# in api/services/metrics.py.
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.db import get_session
from api.errors import HelmError
from api.models import SimState
from api.services import metrics

router = APIRouter(tags=["compare"])


@router.get("/compare")
def get_compare(db: Session = Depends(get_session)):
    sim = db.get(SimState, 1)
    if sim is None:
        raise HelmError(
            "NOT_FOUND", "simulation not initialized - call POST /sim/reset first", 404
        )
    return metrics.compute(db, sim.sim_day, sim.as_of)
