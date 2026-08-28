# api/routers/state.py — B3 made /state real; B4 routes it through the shared
# state_builder so GET /state and build_state() are the same code path (docs/backend/
# 07-PHASE-B4-state-builder-and-engine.md step 1). /forecast now calls the engine gateway
# (docs/backend/06-PHASE-B3-read-routes.md step 3, option 1) instead of the raw fixture.
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from api.db import get_session
from api.enums import POLICIES
from api.errors import HelmError
from api.services.engine_gateway import forecast as gateway_forecast
from api.services.engine_gateway import validated_forecast
from api.services.state_builder import build_state

router = APIRouter(tags=["state"])


def _require_policy(policy: str) -> str:
    if policy not in POLICIES:
        raise HelmError(
            "VALIDATION", f"policy must be one of {POLICIES}", 400, {"policy": policy}
        )
    return policy


@router.get("/state")
def get_state(policy: str = Query("AGENT"), db: Session = Depends(get_session)):
    policy = _require_policy(policy)
    return build_state(db, policy).model_dump(mode="json")


@router.get("/forecast")
def get_forecast(
    horizon: int = Query(90), policy: str = Query("AGENT"), db: Session = Depends(get_session)
):
    policy = _require_policy(policy)
    state = build_state(db, policy)
    fc, _source = gateway_forecast(state, horizon_days=horizon)
    return validated_forecast(fc)
