# api/services/materiality.py — B6. FINAL.md section 11.7 / docs/backend/
# 09-PHASE-B6-events-materiality-ws.md section 3. Decides whether an injected event is worth
# re-solving for.
#
#   materiality = |Δ deployable_cash| / max(cash_available, 1)
#                 + 0.5 × |Δ P(any shortfall in horizon)|
#                 + 1.0 if feasibility of any hard obligation changed
#
# Pure scoring only — it takes two already-computed Forecast dicts (before/after the event
# was applied) and does not call the engine itself. The two forecast() calls happen in
# api/routers/events.py, which owns the "forecast-before, apply, forecast-after" sequence
# (section 3, steps 1-3) because that sequence also drives the event applier and the
# broadcasts in between.
from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from api import config
from api.models import Obligation


def _max_shortfall_prob(forecast: dict) -> float:
    """P(any shortfall in horizon) = max(bucket.shortfall_prob for bucket in buckets)."""
    buckets = forecast.get("buckets") or []
    return max((float(b["shortfall_prob"]) for b in buckets), default=0.0)


def _hard_obligation_feasibility(
    session: Session, forecast: dict, as_of: date
) -> dict[str, bool]:
    """For every unsettled hard obligation: does its due-date bucket's P90 balance sit at or
    above zero? Keyed by obligation id so before/after can be compared one-to-one. An
    obligation whose due date falls outside the forecast horizon has no bucket to check and
    is treated as infeasible=False consistently on both sides, so it never causes a false
    "feasibility changed" flip on its own.
    """
    buckets = {b["day_offset"]: b for b in (forecast.get("buckets") or [])}
    rows = (
        session.query(Obligation)
        .filter(Obligation.hard.is_(True), Obligation.settled_on.is_(None))
        .all()
    )
    out: dict[str, bool] = {}
    for obl in rows:
        offset = (obl.due_date - as_of).days
        bucket = buckets.get(offset)
        out[obl.id] = bucket is not None and float(bucket["p90"]) >= 0
    return out


def _feasibility_changed(
    session: Session, forecast_before: dict, forecast_after: dict, as_of: date
) -> bool:
    before = _hard_obligation_feasibility(session, forecast_before, as_of)
    after = _hard_obligation_feasibility(session, forecast_after, as_of)
    return any(before.get(k) != after.get(k) for k in set(before) | set(after))


def score(
    session: Session,
    forecast_before: dict,
    forecast_after: dict,
    cash_available: float,
    as_of: date,
) -> tuple[float, dict]:
    """Returns (materiality, detail). `detail` carries the before/after numbers the caller
    logs — section 3's "log both outcomes" requirement."""
    deployable_before = float(forecast_before.get("deployable_cash", 0.0))
    deployable_after = float(forecast_after.get("deployable_cash", 0.0))
    shortfall_before = _max_shortfall_prob(forecast_before)
    shortfall_after = _max_shortfall_prob(forecast_after)
    feasibility_changed = _feasibility_changed(
        session, forecast_before, forecast_after, as_of
    )

    materiality = (
        abs(deployable_after - deployable_before) / max(cash_available, 1.0)
        + 0.5 * abs(shortfall_after - shortfall_before)
        + (1.0 if feasibility_changed else 0.0)
    )

    detail = {
        "deployable_before": deployable_before,
        "deployable_after": deployable_after,
        "shortfall_prob_before": shortfall_before,
        "shortfall_prob_after": shortfall_after,
        "feasibility_changed": feasibility_changed,
    }
    return materiality, detail


def is_material(materiality: float) -> bool:
    return materiality >= config.MATERIALITY_THRESHOLD
