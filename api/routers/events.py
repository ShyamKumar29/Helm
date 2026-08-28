# api/routers/events.py — B3 made GET /events real. B6 makes POST /events real (materiality
# scoring, event application, conditional re-solve) and adds WS /api/stream, per
# docs/backend/09-PHASE-B6-events-materiality-ws.md.
from __future__ import annotations

import logging
from typing import get_args

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api import config
from api.db import SessionLocal, get_session
from api.enums import POLICY_AGENT
from api.errors import HelmError
from api.models import Decision, Event, SimState
from api.services import event_apply, ids, materiality
from api.services import metrics as metrics_service
from api.services.engine_gateway import decide as gateway_decide
from api.services.engine_gateway import forecast as gateway_forecast
from api.services.engine_gateway import validated_decision, validated_forecast
from api.services.serializers import event_out
from api.services.state_builder import build_state
from api.services.ws import hub
from contracts.enums import EventType

log = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

EVENT_TYPES = frozenset(get_args(EventType))


class EventBody(BaseModel):
    type: str
    source: str = "JUDGE_INJECTED"
    payload: dict = {}


@router.get("/events")
def list_events(limit: int = Query(50), db: Session = Depends(get_session)):
    rows = (
        db.query(Event)
        .order_by(Event.sim_day.desc(), Event.created_at.desc())
        .limit(limit)
        .all()
    )
    return [event_out(r) for r in rows]


# --------------------------------------------------------------------------------------
# small helpers, duplicated from decisions.py / sim_loop.py on purpose — routers never
# import other routers, services never import routers (00-BACKEND-OVERVIEW.md section 3)
# --------------------------------------------------------------------------------------


def _next_event_id(db: Session) -> str:
    n = db.query(Event).count() + 1
    return ids.event_id(n)


def _next_decision_id(db: Session) -> str:
    n = db.query(Decision).count() + 1
    return ids.decision_id(n)


def _previous_decision(db: Session, policy: str) -> dict | None:
    row = (
        db.query(Decision)
        .filter(Decision.policy == policy)
        .order_by(Decision.sim_day.desc(), Decision.created_at.desc())
        .first()
    )
    return dict(row.payload) if row is not None else None


def _try_attach_explanation(
    db: Session, row: Decision, decision_id: str
) -> dict | None:
    try:
        import httpx

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
        log.warning(
            "explainer unavailable, decision %s has no explanation", decision_id
        )
        return None


def _reoptimize(
    db: Session, event_id: str, materiality_score: float, state
) -> dict | None:
    """Section 4 step 9. Never allowed to fail the event itself (Bulletproofing) — any
    exception here degrades to `decision: null`, logged loudly, not raised."""
    try:
        previous = _previous_decision(db, POLICY_AGENT)
        trigger = {
            "type": "EVENT",
            "event_id": event_id,
            "materiality_score": materiality_score,
            "description": f"triggered by {event_id}",
        }
        decision_dict, source = gateway_decide(
            state, weights=None, previous=previous, trigger=trigger
        )
        decision_dict["decision_id"] = _next_decision_id(db)
        decision_dict["run_at"] = state.as_of.isoformat()
        decision_dict["sim_day"] = state.sim_day
        decision_dict["policy"] = POLICY_AGENT
        validated = validated_decision(decision_dict)
    except Exception:
        log.exception("re-optimize failed for event %s, decision stays null", event_id)
        return None

    log.info(
        "decision %s source=%s trigger=EVENT event=%s materiality=%.2f",
        validated["decision_id"],
        source,
        event_id,
        materiality_score,
    )

    row = Decision(
        decision_id=validated["decision_id"],
        sim_day=validated["sim_day"],
        run_at=state.as_of,
        policy=POLICY_AGENT,
        payload=validated,
        explanation=None,
    )
    db.add(row)
    db.commit()

    ev = db.get(Event, event_id)
    if ev is not None:
        ev.triggered_reoptimization = True
        ev.triggered_decision_id = validated["decision_id"]
        db.commit()

    explanation = _try_attach_explanation(db, row, validated["decision_id"])
    validated["explanation"] = explanation
    return validated


# --------------------------------------------------------------------------------------
# POST /events — section 4's ten-step algorithm, in order
# --------------------------------------------------------------------------------------


@router.post("/events")
async def inject_event(body: EventBody, db: Session = Depends(get_session)):
    # step 1 — type is in the frozen EventType enum
    if body.type not in EVENT_TYPES:
        raise HelmError(
            "VALIDATION", f"unknown event type {body.type!r}", 400, {"type": body.type}
        )

    # step 2 — payload shape (and existence) for that type. Nothing persisted yet: a
    # malformed or unresolvable event changes nothing in the DB (Bulletproofing).
    event_apply.validate(db, body.type, body.payload)
    applier = event_apply.APPLIERS[body.type]

    sim = db.get(SimState, 1)
    if sim is None:
        raise HelmError(
            "NOT_FOUND", "simulation not initialized - call POST /sim/reset first", 404
        )
    sim_day, as_of = sim.sim_day, sim.as_of

    # step 3 — assign event_id; date/sim_day from sim_state
    event_id = _next_event_id(db)

    # step 4 — persist the event row (materiality_score filled in at step 7)
    row = Event(
        event_id=event_id,
        sim_day=sim_day,
        date=as_of,
        type=body.type,
        source=body.source,
        payload=body.payload,
        materiality_score=None,
        triggered_reoptimization=False,
        triggered_decision_id=None,
    )
    db.add(row)
    db.commit()

    # step 5 — broadcast on channel "event"
    await hub.send("event", sim_day, event_out(row))

    # step 6 — forecast-before, apply, forecast-after, score materiality
    try:
        state_before = build_state(db, POLICY_AGENT)
        fc_before, _ = gateway_forecast(state_before, horizon_days=config.HORIZON_DAYS)

        ctx = event_apply.ApplyContext(sim_day=sim_day, as_of=as_of)
        try:
            applier(db, body.payload, ctx)
            db.commit()
        except Exception:
            db.rollback()
            raise

        state_after = build_state(db, POLICY_AGENT)
        fc_after, _ = gateway_forecast(state_after, horizon_days=config.HORIZON_DAYS)

        score_value, detail = materiality.score(
            db, fc_before, fc_after, state_before.cash_available, as_of
        )
    except HelmError:
        raise
    except Exception:
        log.exception("event %s failed to apply, rolling back", event_id)
        db.rollback()
        raise HelmError(
            "INTERNAL", "failed to apply event", 500, {"event_id": event_id}
        )

    # step 7 — persist materiality_score on the event row
    row.materiality_score = score_value
    db.commit()

    # step 8 — broadcast a "log" frame with the threshold comparison (both outcomes)
    material = materiality.is_material(score_value)
    if material:
        text = (
            f"Event {event_id} materiality {score_value:.2f} "
            f">= threshold {config.MATERIALITY_THRESHOLD:.2f} - re-optimising"
        )
    else:
        text = (
            f"Event {event_id} materiality {score_value:.2f} "
            f"< threshold {config.MATERIALITY_THRESHOLD:.2f} - no change needed"
        )
    log.info(text)
    await hub.send("log", sim_day, {"level": "info", "text": text})

    # step 9 — if material: build state, decide, validate, persist, attach explanation,
    # broadcast on "decision" and "forecast". `state_after` is already the post-event state.
    decision_dict = None
    if material:
        decision_dict = _reoptimize(db, event_id, score_value, state_after)
        if decision_dict is not None:
            await hub.send("decision", sim_day, decision_dict)
            # A broadcast is never allowed to turn an already-committed decision into a
            # failed request (Bulletproofing) — a bad forecast shape here is an engine bug,
            # logged loudly, not a reason to 500 a response the judge is watching.
            try:
                await hub.send("forecast", sim_day, validated_forecast(fc_after))
            except Exception:
                log.exception(
                    "event %s: forecast broadcast skipped, bad shape", event_id
                )
        else:
            await hub.send(
                "log",
                sim_day,
                {
                    "level": "warn",
                    "text": f"Event {event_id} re-optimization degraded - decision unavailable",
                },
            )

    # step 10 — recompute metrics, broadcast on "metrics". Never allowed to fail an
    # already-committed event/decision (Bulletproofing, same rule as the forecast
    # broadcast above) — a bad metrics computation is logged loudly, not raised.
    try:
        comparison = metrics_service.compute(db, sim_day, as_of)
        await hub.send("metrics", sim_day, comparison)
    except Exception:
        log.exception(
            "event %s: metrics broadcast skipped, computation failed", event_id
        )

    return {"event": event_out(row), "decision": decision_dict}


# --------------------------------------------------------------------------------------
# WS /api/stream — section 5. Mounted on this already-included router (not a new one) so
# nothing in api/main.py has to change (CLAUDE.md rule B1 / 01-OWNERSHIP-AND-CONFLICT-
# RULES.md 2.2: "adding a route later means editing a file in api/routers/, never main.py").
# --------------------------------------------------------------------------------------


async def _send_snapshot(ws: WebSocket) -> None:
    """On connect: current sim, newest metrics, newest forecast (section 5) — computed live
    so a reload never sits on a stale or empty dashboard waiting for the next tick. Wrapped
    end to end: a client that drops mid-snapshot must not raise into the server.

    All three frames are gated on a simulation existing (`sim is not None`) — B7 makes the
    metrics frame a real `ComparisonMetrics` computed from the ledger/invoices, and there is
    nothing meaningful to compute before the first `POST /sim/reset`. The B6 fixture-backed
    version sent a "metrics" frame unconditionally; this brings it in line with the "sim" and
    "forecast" frames, which were already gated the same way.
    """
    db = SessionLocal()
    try:
        sim = db.get(SimState, 1)
        sim_day = sim.sim_day if sim is not None else 0

        if sim is not None:
            await ws.send_json(
                {
                    "channel": "sim",
                    "sim_day": sim_day,
                    "data": {
                        "sim_day": sim.sim_day,
                        "as_of": sim.as_of.isoformat(),
                        "running": sim.running,
                        "horizon_days": sim.horizon_days,
                    },
                }
            )

            comparison = metrics_service.compute(db, sim.sim_day, sim.as_of)
            await ws.send_json(
                {"channel": "metrics", "sim_day": sim_day, "data": comparison}
            )

            state = build_state(db, POLICY_AGENT)
            fc, _ = gateway_forecast(state, horizon_days=config.HORIZON_DAYS)
            await ws.send_json({"channel": "forecast", "sim_day": sim_day, "data": fc})
    except Exception:
        log.warning(
            "snapshot on connect failed, client will catch up on the next broadcast",
            exc_info=True,
        )
    finally:
        db.close()


@router.websocket("/stream")
async def stream(ws: WebSocket) -> None:
    await hub.connect(ws)
    await _send_snapshot(ws)
    try:
        while True:
            # We never expect inbound frames; this just parks the coroutine until the
            # client disconnects, which is the only way to detect it (section 5 rule:
            # killing/reconnecting a client must never raise anywhere in the API).
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        hub.disconnect(ws)
