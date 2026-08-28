# api/routers/decisions.py — B3 made GET /decisions and GET /decisions/{id} real.
# B4 makes POST /decide and POST /weights real, through the engine gateway
# (docs/backend/07-PHASE-B4-state-builder-and-engine.md steps 4-6).
import logging

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.db import get_session
from api.enums import POLICIES, POLICY_AGENT
from api.errors import HelmError
from api.models import Decision, SimState
from api.services import ids
from api.services.engine_gateway import decide as gateway_decide
from api.services.engine_gateway import validated_decision
from api.services.state_builder import build_state

log = logging.getLogger(__name__)

router = APIRouter(tags=["decisions"])


class DecideBody(BaseModel):
    weights: dict | None = None
    reason: str = "MANUAL"


class WeightsBody(BaseModel):
    discount: float
    financing_cost: float
    penalty: float
    liquidity_risk: float
    supplier_stress: float


@router.get("/decisions")
def list_decisions(
    policy: str = Query("AGENT"),
    limit: int = Query(20),
    db: Session = Depends(get_session),
):
    if policy not in POLICIES:
        raise HelmError(
            "VALIDATION", f"policy must be one of {POLICIES}", 400, {"policy": policy}
        )

    rows = (
        db.query(Decision)
        .filter(Decision.policy == policy)
        .order_by(Decision.sim_day.desc(), Decision.created_at.desc())
        .limit(limit)
        .all()
    )
    # Return the stored payload as-is, explanation merged in. Do not reshape, do not
    # re-round, do not add fields — it was already validated on the way in.
    out = []
    for row in rows:
        obj = dict(row.payload)
        obj["explanation"] = row.explanation
        out.append(obj)
    return out


@router.get("/decisions/{decision_id}")
def get_decision(decision_id: str, db: Session = Depends(get_session)):
    row = db.get(Decision, decision_id)
    if row is None:
        raise HelmError(
            "NOT_FOUND", f"no decision {decision_id}", 404, {"decision_id": decision_id}
        )
    obj = dict(row.payload)
    obj["explanation"] = row.explanation
    return obj


def _previous_decision(db: Session, policy: str) -> dict | None:
    row = (
        db.query(Decision)
        .filter(Decision.policy == policy)
        .order_by(Decision.sim_day.desc(), Decision.created_at.desc())
        .first()
    )
    return dict(row.payload) if row is not None else None


def _next_decision_id(db: Session) -> str:
    # Counter from a COUNT(*) inside the caller's transaction (api/services/ids.py
    # convention) — good enough for a single-writer hackathon demo, not a distributed system.
    n = db.query(Decision).count() + 1
    return ids.decision_id(n)


def _run_decision(db: Session, policy: str, weights: dict | None, trigger: dict) -> dict:
    """Shared by POST /decide and POST /weights: build state, call the engine gateway,
    stamp the simulation facts the engine cannot know, validate, persist, try to attach
    an explanation, return the finished DecisionObject."""
    state = build_state(db, policy)  # raises HelmError 404 if sim not initialized
    previous = _previous_decision(db, policy)

    decision_dict, source = gateway_decide(
        state, weights=weights, previous=previous, trigger=trigger
    )

    # The one exception to "never patch the engine's output" (phase B4 step 3): these four
    # fields are simulation facts the engine cannot know, not decision content.
    decision_dict["decision_id"] = _next_decision_id(db)
    decision_dict["run_at"] = state.as_of.isoformat()
    decision_dict["sim_day"] = state.sim_day
    decision_dict["policy"] = policy

    validated = validated_decision(decision_dict)
    log.info("decision %s source=%s trigger=%s", validated["decision_id"], source, trigger["type"])

    row = Decision(
        decision_id=validated["decision_id"],
        sim_day=validated["sim_day"],
        run_at=state.as_of,
        policy=policy,
        payload=validated,
        explanation=None,
    )
    db.add(row)
    db.commit()

    explanation = _try_attach_explanation(db, row, validated["decision_id"])
    validated["explanation"] = explanation
    return validated


def _try_attach_explanation(db: Session, row: Decision, decision_id: str) -> dict | None:
    """Internal call to our own /explain/{id}, never allowed to fail the request
    (docs/backend/07-PHASE-B4 step 6 / 00-BACKEND-OVERVIEW.md section 4.2)."""
    try:
        import httpx

        from api import config

        resp = httpx.post(
            f"{config.API_SELF_BASE_URL}/explain/{decision_id}",
            json={"mode": config.EXPLAINER_MODE},
            timeout=3.0,
        )
        resp.raise_for_status()
        explanation = resp.json()
        row.explanation = explanation
        db.commit()
        return explanation
    except Exception:
        log.warning("explainer unavailable, decision %s has no explanation", decision_id)
        return None


@router.post("/decide")
def decide(body: DecideBody, db: Session = Depends(get_session)):
    trigger = {
        "type": "MANUAL",
        "event_id": None,
        "materiality_score": None,
        "description": body.reason,
    }
    return _run_decision(db, POLICY_AGENT, body.weights, trigger)


@router.post("/weights")
def set_weights(body: WeightsBody, db: Session = Depends(get_session)):
    sim = db.get(SimState, 1)
    if sim is None:
        raise HelmError(
            "NOT_FOUND", "simulation not initialized - call POST /sim/reset first", 404
        )

    weights = body.model_dump()
    sim.weights = weights
    db.add(sim)
    db.commit()

    trigger = {
        "type": "MANUAL",
        "event_id": None,
        "materiality_score": None,
        "description": "weights changed via POST /weights",
    }
    decision = _run_decision(db, POLICY_AGENT, weights, trigger)
    return {"weights": weights, "decision": decision}
