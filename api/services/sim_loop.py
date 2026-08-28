# api/services/sim_loop.py — B5. The eight-step day loop (docs/backend/08-PHASE-B5-sim-loop.md
# section 3 / FINAL.md section 13). Each step is a separate, separately testable function;
# `advance_one_day()` is the only thing that calls them in order.
#
# Cash only ever moves through api/services/ledger.py. The only randomness in the whole sim
# loop comes from api/services/rng.py, seeded from `sim_state.seed` — never a bare
# `random.*`/`np.random.*` call anywhere in this file.
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from api import config
from api.baseline import static_rules as baseline_rules
from api.enums import POLICIES, POLICY_AGENT, POLICY_BASELINE
from api.errors import HelmError
from api.models import Customer, Decision, Event, Obligation, Receivable, SimState
from api.services import clock, executor, ids, ledger, rng
from api.services import metrics as metrics_service
from api.services.engine_gateway import decide as gateway_decide
from api.services.engine_gateway import validated_decision
from api.services.state_builder import build_state

log = logging.getLogger(__name__)


@dataclass
class DayContext:
    """Everything the day's steps need to agree on. Not a contract type — internal to the
    sim loop only."""

    sim_day: int
    as_of: date
    seed: int
    weights: dict
    events: list[dict] = field(default_factory=list)
    _event_n: int = 0

    def next_event_id(self) -> str:
        self._event_n += 1
        return ids.event_id(self._event_n)


@dataclass
class DayResult:
    sim_day: int
    events: list[dict]
    decisions: list[dict]
    metrics: dict  # internal only — not part of the frozen /sim/step response shape


# --------------------------------------------------------------------------------------
# Step 1 — advance the clock
# --------------------------------------------------------------------------------------


def step_1_advance_clock(session: Session) -> DayContext:
    sim_row = session.get(SimState, 1)
    if sim_row is None:
        raise HelmError(
            "NOT_FOUND", "simulation not initialized - call POST /sim/reset first", 404
        )

    sim_row.sim_day += 1
    sim_row.as_of = clock.advance(sim_row.as_of)
    session.flush()

    ctx = DayContext(
        sim_day=sim_row.sim_day,
        as_of=sim_row.as_of,
        seed=sim_row.seed,
        weights=dict(sim_row.weights),
        _event_n=session.query(Event).count(),
    )
    event = executor.emit_event(
        session,
        ctx,
        "DAY_ADVANCED",
        {
            "new_sim_day": ctx.sim_day,
            "new_date": ctx.as_of.isoformat(),
        },
    )
    ctx.events.append(event)
    return ctx


# --------------------------------------------------------------------------------------
# Step 2 — roll receivable arrivals
# --------------------------------------------------------------------------------------


def step_2_roll_receivables(session: Session, sim: DayContext) -> list[dict]:
    events: list[dict] = []
    customers = {c.id: c for c in session.query(Customer).all()}
    open_rcvs = session.query(Receivable).filter(Receivable.status == "OPEN").all()

    for r in open_rcvs:
        customer = customers.get(r.customer_id)
        if customer is None:
            continue  # orphan reference — not a B5 concern

        draw = rng.gen(sim.seed, r.id)
        delay_days = rng.sample_delay(
            draw,
            mean_delay_days=customer.mean_delay_days,
            std_delay_days=customer.std_delay_days,
            on_time_probability=customer.on_time_probability,
            historical_delays=customer.historical_delays,
        )
        realised_arrival = clock.add_days(r.expected_date, delay_days)
        if sim.as_of != realised_arrival:
            continue

        r.status = "COLLECTED"
        r.actual_date = sim.as_of
        session.flush()

        for policy in POLICIES:
            ledger.post(
                session,
                policy,
                sim.sim_day,
                sim.as_of,
                float(r.amount),
                "RECEIVABLE_COLLECTED",
                r.id,
            )

        events.append(
            executor.emit_event(
                session,
                sim,
                "RECEIVABLE_COLLECTED",
                {
                    "receivable_id": r.id,
                    "amount": round(float(r.amount), 2),
                    "days_late": clock.days_between(sim.as_of, r.expected_date),
                },
            )
        )

    return events


# --------------------------------------------------------------------------------------
# Step 3 — apply due obligations
# --------------------------------------------------------------------------------------


def step_3_apply_obligations(session: Session, sim: DayContext) -> list[dict]:
    due = (
        session.query(Obligation)
        .filter(Obligation.settled_on.is_(None), Obligation.due_date == sim.as_of)
        .all()
    )
    for obl in due:
        for policy in POLICIES:
            # Never blocked: a negative balance here IS the baseline's story (section 3).
            ledger.post(
                session,
                policy,
                sim.sim_day,
                sim.as_of,
                -float(obl.amount),
                "OBLIGATION",
                obl.id,
            )
        # Applied identically and unconditionally to both policies — obligation payment is
        # never a decision, so one settled_on stamp is correct. Per-policy divergence, if it
        # ever mattered, is read from the ledger (reason="OBLIGATION", ref_id=obl.id), not
        # this column (section 3 step 3).
        obl.settled_on = sim.as_of

    session.flush()
    return []  # no EventType exists for a due obligation (contracts/enums.py)


# --------------------------------------------------------------------------------------
# Step 4 — execute scheduled actions
# --------------------------------------------------------------------------------------


def step_4_execute_scheduled_actions(session: Session, sim: DayContext) -> list[dict]:
    events: list[dict] = []
    for policy in POLICIES:
        events += executor.execute_scheduled_actions(session, sim, policy)
    return events


# --------------------------------------------------------------------------------------
# Step 5 — materiality (placeholder; real scoring is B6)
# --------------------------------------------------------------------------------------


def step_5_score_materiality(
    session: Session, sim: DayContext, events: list[dict]
) -> float:
    """Placeholder per docs/backend/08-PHASE-B5-sim-loop.md section 3 step 5: real scoring
    (FINAL.md section 11.7) lands in api/services/materiality.py, B6. This is enough to keep
    the loop moving: 1.0 whenever anything besides the clock tick happened, else 0.0."""
    if any(e["type"] != "DAY_ADVANCED" for e in events):
        return 1.0
    return 0.0


# --------------------------------------------------------------------------------------
# Step 6 — maybe re-optimise (AGENT only)
# --------------------------------------------------------------------------------------


def _next_decision_id(session: Session) -> str:
    # Local counter rather than api/routers/decisions.py's — services never import routers
    # (00-BACKEND-OVERVIEW.md section 3). Same convention: COUNT(*) inside the caller's
    # transaction, good enough for a single-writer hackathon demo.
    n = session.query(Decision).count() + 1
    return ids.decision_id(n)


def _previous_decision(session: Session, policy: str) -> dict | None:
    row = (
        session.query(Decision)
        .filter(Decision.policy == policy)
        .order_by(Decision.sim_day.desc(), Decision.created_at.desc())
        .first()
    )
    return dict(row.payload) if row is not None else None


def _attach_explanation(
    session: Session, decision_row: Decision, decision_id: str
) -> dict | None:
    """Best-effort internal call to our own /explain/{id}. Duplicates api/routers/
    decisions.py's `_try_attach_explanation` on purpose rather than importing it — services
    never import routers (00-BACKEND-OVERVIEW.md section 3)."""
    try:
        import httpx

        resp = httpx.post(
            f"{config.API_SELF_BASE_URL}/explain/{decision_id}",
            json={"mode": config.EXPLAINER_MODE},
            timeout=3.0,
        )
        resp.raise_for_status()
        explanation = resp.json()
        decision_row.explanation = explanation
        session.commit()
        return explanation
    except Exception:
        log.warning(
            "explainer unavailable, decision %s has no explanation", decision_id
        )
        return None


def step_6_maybe_reoptimize(
    session: Session, sim: DayContext, events: list[dict], materiality: float
) -> dict | None:
    """AGENT only. The day loop's own decide() call *is* the scheduled daily run (FINAL.md
    section 13 step 6 / the "treasurer decides every morning" pitch in CLAUDE.md) — it always
    fires once per simulated day. The materiality gate matters for B6's out-of-band
    judge-injected events (`POST /events`), not this cadence; it is still computed and logged
    here so the decline path this phase's placeholder can reach is visible in the log.
    """
    scheduled_daily_run = True
    if not (materiality >= config.MATERIALITY_THRESHOLD or scheduled_daily_run):
        log.info(
            "sim_day %s: materiality %.2f < threshold %.2f - no change needed",
            sim.sim_day,
            materiality,
            config.MATERIALITY_THRESHOLD,
        )
        return None

    state = build_state(session, POLICY_AGENT)
    previous = _previous_decision(session, POLICY_AGENT)
    trigger = {
        "type": "SCHEDULED",
        "event_id": None,
        "materiality_score": materiality,
        "description": "scheduled daily re-optimization",
    }
    decision_dict, source = gateway_decide(
        state, weights=sim.weights, previous=previous, trigger=trigger
    )

    # Simulation facts the engine cannot know (docs/backend/07-PHASE-B4 step 3) — the one
    # allowed patch onto the engine's output.
    decision_dict["decision_id"] = _next_decision_id(session)
    decision_dict["run_at"] = state.as_of.isoformat()
    decision_dict["sim_day"] = state.sim_day
    decision_dict["policy"] = POLICY_AGENT

    validated = validated_decision(decision_dict)
    log.info(
        "decision %s source=%s sim_day=%s materiality=%.2f",
        validated["decision_id"],
        source,
        sim.sim_day,
        materiality,
    )

    row = Decision(
        decision_id=validated["decision_id"],
        sim_day=validated["sim_day"],
        run_at=state.as_of,
        policy=POLICY_AGENT,
        payload=validated,
        explanation=None,
    )
    session.add(row)
    # Committed here (not at the day's final commit) because attaching an explanation is an
    # internal HTTP round trip that needs the decision already visible to the explainer's own
    # DB connection — same tradeoff api/routers/decisions.py's `_run_decision` makes.
    session.commit()

    explanation = _attach_explanation(session, row, validated["decision_id"])
    validated["explanation"] = explanation
    return validated


# --------------------------------------------------------------------------------------
# Step 7 — run the baseline. Real agent, B7 (FINAL.md section 11.8 / docs/backend/
# 10-PHASE-B7-baseline-and-metrics.md).
# --------------------------------------------------------------------------------------


def step_7_run_baseline(session: Session, sim: DayContext) -> dict | None:
    """BASELINE only. Runs every simulated day, unconditionally — the static rule has no
    materiality gate and no re-optimisation concept (FINAL.md section 11.8: "No
    re-optimisation"). Mirrors step 6's stamping pattern: the agent module returns a dict
    without decision_id/run_at/sim_day/policy, which are simulation facts it cannot know
    about itself."""
    decision_dict = baseline_rules.run(session, sim)
    decision_dict["decision_id"] = _next_decision_id(session)
    decision_dict["run_at"] = sim.as_of.isoformat()
    decision_dict["sim_day"] = sim.sim_day
    decision_dict["policy"] = POLICY_BASELINE

    validated = validated_decision(decision_dict)
    log.info(
        "baseline decision %s sim_day=%s actions=%d",
        validated["decision_id"],
        sim.sim_day,
        len(validated["actions"]),
    )

    row = Decision(
        decision_id=validated["decision_id"],
        sim_day=validated["sim_day"],
        run_at=sim.as_of,
        policy=POLICY_BASELINE,
        payload=validated,
        explanation=None,
    )
    session.add(row)
    session.flush()
    return validated


# --------------------------------------------------------------------------------------
# Step 8 — recompute metrics. Real ComparisonMetrics, B7 (FINAL.md section 8.7 / docs/
# backend/10-PHASE-B7-baseline-and-metrics.md section 4).
# --------------------------------------------------------------------------------------


def step_8_recompute_metrics(session: Session, sim: DayContext) -> dict:
    """Internal only: `DayResult.metrics` is not part of the frozen `/sim/step` response
    shape (FINAL.md section 10) — callers that need it on the wire read it from
    `GET /compare` or the WS `metrics` channel, both backed by the same
    api/services/metrics.compute()."""
    return metrics_service.compute(session, sim.sim_day, sim.as_of)


# --------------------------------------------------------------------------------------
# The loop
# --------------------------------------------------------------------------------------


def advance_one_day(session: Session) -> DayResult:
    """One transaction for the world-state steps (1-4): if a day fails halfway, the whole
    day's cash/receivable/obligation/action writes roll back together. Step 6's decision
    insert commits separately for the reason documented on `_attach_explanation` above."""
    try:
        events: list[dict] = []
        sim = step_1_advance_clock(session)
        events += sim.events
        events += step_2_roll_receivables(session, sim)
        events += step_3_apply_obligations(session, sim)
        events += step_4_execute_scheduled_actions(session, sim)
        session.commit()
    except Exception:
        session.rollback()
        raise

    material = step_5_score_materiality(session, sim, events)

    decisions: list[dict] = []
    decision = step_6_maybe_reoptimize(session, sim, events, material)
    if decision is not None:
        decisions.append(decision)

    baseline = step_7_run_baseline(session, sim)
    if baseline is not None:
        decisions.append(baseline)

    metrics = step_8_recompute_metrics(session, sim)
    session.commit()

    return DayResult(
        sim_day=sim.sim_day, events=events, decisions=decisions, metrics=metrics
    )
