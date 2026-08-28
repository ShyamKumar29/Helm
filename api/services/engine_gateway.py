# api/services/engine_gateway.py — B4. The ONLY import site for engine/ in all of api/.
#
# Three guarantees this buys (docs/backend/07-PHASE-B4-state-builder-and-engine.md):
#   1. The API never hangs — an outer timeout on top of the engine's own 2s internal budget,
#      for the case where that timeout itself fails.
#   2. The API never 500s because of the engine — any exception degrades to the last
#      known-good fixture shape and logs loudly.
#   3. One place to change when Shyam changes something.
#
# Nothing here patches a bad DecisionObject/Forecast into shape. A shape that fails
# `contracts.schemas` validation is Shyam's bug, reported out loud with the field name —
# not silently corrected in api/ (CLAUDE.md rule 6 / docs/backend B6).
import json
import logging
import pathlib
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout

from api import config
from contracts.schemas import DecisionObject, Forecast, State

log = logging.getLogger(__name__)

_FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
_POOL = ThreadPoolExecutor(max_workers=2)

try:
    from engine.decide import decide as _decide
    from engine.decide import forecast as _forecast

    ENGINE_AVAILABLE = True
except Exception as e:  # engine absent or broken — this is the contract, not a bug
    log.warning("engine not importable, serving fixtures: %s", e)
    ENGINE_AVAILABLE = False


def _fixture(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def _as_dict(result) -> dict:
    """The engine may return a Pydantic model or a plain dict depending on how far along
    it is. Normalise to a dict either way."""
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return result


def _budget_s() -> float:
    # engine's own internal timeout (config.SOLVER_TIMEOUT_MS) plus our outer margin.
    return (config.SOLVER_TIMEOUT_MS + 1500) / 1000.0


def decide(
    state: State,
    weights: dict | None = None,
    previous: dict | None = None,
    trigger: dict | None = None,
) -> tuple[dict, str]:
    """Returns (decision_dict, source) where source is 'engine' | 'fixture' | 'degraded'."""
    if not ENGINE_AVAILABLE:
        return _fixture("decision.sample.json"), "fixture"

    fut = _POOL.submit(_decide, state, weights=weights, previous=previous, trigger=trigger)
    try:
        result = fut.result(timeout=_budget_s())
    except FuturesTimeout:
        log.error("engine.decide exceeded %.1fs budget", _budget_s())
        return _fixture("decision.sample.json"), "degraded"
    except Exception:
        log.exception("engine.decide raised")
        return _fixture("decision.sample.json"), "degraded"
    return _as_dict(result), "engine"


def forecast(state: State, horizon_days: int = 90) -> tuple[dict, str]:
    """Returns (forecast_dict, source). Same three guarantees as decide()."""
    if not ENGINE_AVAILABLE:
        return _fixture("forecast.sample.json"), "fixture"

    fut = _POOL.submit(_forecast, state, horizon_days=horizon_days)
    try:
        result = fut.result(timeout=_budget_s())
    except FuturesTimeout:
        log.error("engine.forecast exceeded %.1fs budget", _budget_s())
        return _fixture("forecast.sample.json"), "degraded"
    except Exception:
        log.exception("engine.forecast raised")
        return _fixture("forecast.sample.json"), "degraded"
    return _as_dict(result), "engine"


def validated_decision(decision: dict) -> dict:
    """Validate an engine (or fixture) decision against the frozen contract.

    Never patch a bad shape here — see module docstring. The one explicitly allowed
    exception (phase B4 step 3): callers may stamp `decision_id`, `run_at`, `sim_day` and
    `policy` onto the dict *before* calling this, because those are simulation facts the
    engine cannot know. Nothing else gets touched here.

    `by_alias=True` matters for exactly one field in the whole contract set:
    `DiffFlip.from_` (contracts/schemas.py), aliased to the wire name `"from"` because
    `from` is a Python keyword. Without it this dumps the Python attribute name `from_`
    onto the wire, silently breaking `diff_from_previous.flipped[].from` — found while
    wiring up B7's baseline `diff_from_previous` (docs/backend/
    10-PHASE-B7-baseline-and-metrics.md), which populates this same field for the first
    time in the sim loop; it was equally broken for the AGENT's engine-produced decisions
    before this fix (api/services/sim_loop.py step 6 calls this same function).
    """
    try:
        return DecisionObject.model_validate(decision).model_dump(
            mode="json", by_alias=True
        )
    except Exception:
        log.exception("engine returned an invalid DecisionObject")
        raise


def validated_forecast(fc: dict) -> dict:
    """Validate an engine (or fixture) forecast against the frozen contract."""
    try:
        return Forecast.model_validate(fc).model_dump(mode="json")
    except Exception:
        log.exception("engine returned an invalid Forecast")
        raise
