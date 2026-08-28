# engine/decide.py — the ONLY public contract (FINAL.md §12): `forecast()` and `decide()`.
# Frozen signatures, never change them. `api/services/engine_gateway.py` is the only place in
# `api/` that imports from here, and it imports exactly these two names.
from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

from contracts.schemas import (
    Action,
    DecisionObject,
    DiffFromPrevious,
    Facility,
    FacilityAction,
    Forecast,
    ForecastBucket,
    ObjectiveWeights,
    RejectedAlternative,
    ScoreBreakdown,
    SolverInfo,
    State,
    Trigger,
)
from engine.actions import candidates as candidates_mod
from engine.forecast import liquidity_floor, monte_carlo
from engine.forecast.monte_carlo import MonteCarloResult
from engine.optimizer import greedy_fallback, milp
from engine.diffing import decision_diff
from engine.rng import rng_for

DEFAULT_WEIGHTS = ObjectiveWeights(
    discount=1.0, financing_cost=1.0, penalty=1.0, liquidity_risk=1.5, supplier_stress=0.8
)

DECIDE_HORIZON_DAYS = 90
DECIDE_N_PATHS = 1000  # decide() needs solver time left in its own 2s budget; forecast()
# called directly (GET /forecast) keeps the full 2000-path default below.
SOLVE_BUDGET_S = 2.0


def _build_forecast(state: State, horizon_days: int, n_paths: int, alpha: float) -> tuple[Forecast, MonteCarloResult]:
    rng = rng_for(state)
    mc = monte_carlo.run(state, horizon_days, n_paths, rng)
    floor = liquidity_floor.compute(state, mc, alpha, horizon_days)

    buckets = [
        ForecastBucket(
            date=monte_carlo.bucket_date(state.as_of, t),
            day_offset=t,
            p10=round(float(mc.p10[t]), 2),
            p50=round(float(mc.p50[t]), 2),
            p90=round(float(mc.p90[t]), 2),
            shortfall_prob=round(float(mc.shortfall_prob[t]), 4),
            committed_outflow=round(float(mc.cum_committed[t]), 2),
            expected_inflow=round(float(mc.cum_expected_inflow[t]), 2),
        )
        for t in range(horizon_days + 1)
    ]

    fc = Forecast(
        generated_at=state.as_of,
        sim_day=state.sim_day,
        horizon_days=horizon_days,
        n_paths=n_paths,
        risk_alpha=alpha,
        buckets=buckets,
        deployable_cash=round(floor.deployable_cash, 2),
        buffer_required=round(floor.buffer_required, 2),
        binding_date=floor.binding_date,
        binding_reason=floor.binding_reason,
        worst_case_min_cash=round(floor.worst_case_min_cash, 2),
    )
    return fc, mc


def forecast(state: State, horizon_days: int = 90, n_paths: int = 2000, alpha: float = 0.05) -> Forecast:
    fc, _mc = _build_forecast(state, horizon_days, n_paths, alpha)
    return fc


def _resolve_weights(weights: Any) -> ObjectiveWeights:
    if weights is None:
        return DEFAULT_WEIGHTS
    if isinstance(weights, ObjectiveWeights):
        return weights
    # A plain dict from api/ (every real caller — DecideBody.weights, WeightsBody.model_dump(),
    # sim_state.weights). Missing keys fall back to the matching default rather than raising.
    merged = DEFAULT_WEIGHTS.model_dump()
    merged.update({k: v for k, v in dict(weights).items() if v is not None})
    return ObjectiveWeights(**merged)


def _resolve_trigger(trigger: dict[str, Any] | None) -> Trigger:
    if trigger is None:
        return Trigger(type="MANUAL", event_id=None, materiality_score=None, description=None)
    return Trigger(
        type=trigger.get("type", "MANUAL"),
        event_id=trigger.get("event_id"),
        materiality_score=trigger.get("materiality_score"),
        description=trigger.get("description"),
    )


def _confidence(chosen_score: float, all_scores: list[float]) -> float:
    others = [s for s in all_scores if s != chosen_score]
    if not others:
        return 0.75
    runner_up = max(others)
    spread = abs(chosen_score) + abs(runner_up) + 1.0
    margin = (chosen_score - runner_up) / spread
    return round(min(0.97, max(0.5, 0.6 + 0.4 * margin)), 2)


def _facility_actions(
    chosen: dict[str, candidates_mod.Candidate], as_of, facilities: list[Facility]
) -> list[FacilityAction]:
    facility_by_id = {f.id: f for f in facilities}
    totals: dict[str, dict[str, float]] = {}
    for c in chosen.values():
        if c.facility is None:
            continue
        agg = totals.setdefault(c.facility.id, {"amount": 0.0, "interest": 0.0})
        agg["amount"] += c.amount
        agg["interest"] += c.financing_cost

    out: list[FacilityAction] = []
    for fid, agg in totals.items():
        if agg["amount"] <= 0:
            continue
        fac = facility_by_id[fid]
        out.append(
            FacilityAction(
                facility_id=fid,
                action="DRAW",
                amount=round(agg["amount"], 2),
                expected_repay_date=as_of + timedelta(days=fac.repayment_days),
                interest_cost=round(agg["interest"], 2),
            )
        )
    return out


def decide(
    state: State,
    weights: ObjectiveWeights | dict | None = None,
    previous: DecisionObject | dict | None = None,
    trigger: dict | None = None,
) -> DecisionObject:
    t0 = time.monotonic()
    ow = _resolve_weights(weights)
    previous_dict: dict[str, Any] | None = (
        # by_alias=True: DiffFlip.from_ is aliased to the wire name "from" (contracts/
        # schemas.py) — every real caller already passes a plain dict dumped this way
        # (api/routers/decisions.py, events.py, sim_loop.py); this branch only matters when
        # something calls decide() with the Pydantic object itself (explainer/whatif.py's
        # baseline_decision), and it needs the exact same wire shape to diff against.
        previous.model_dump(mode="json", by_alias=True) if hasattr(previous, "model_dump") else previous
    )

    fc, mc = _build_forecast(state, DECIDE_HORIZON_DAYS, DECIDE_N_PATHS, 0.05)

    if fc.binding_date is not None:
        offset = (fc.binding_date - state.as_of).days
        shortfall_at_binding = fc.buckets[offset].shortfall_prob if 0 <= offset < len(fc.buckets) else 0.0
    else:
        shortfall_at_binding = max((b.shortfall_prob for b in fc.buckets), default=0.0)

    suppliers_by_id = {s.id: s for s in state.suppliers}
    bank_facility = next((f for f in state.facilities if f.type == "BANK_LINE"), None)
    supplier_facility = next((f for f in state.facilities if f.type == "SUPPLIER_FINANCE"), None)

    candidates_by_invoice = {
        inv.id: candidates_mod.generate(
            inv,
            suppliers_by_id.get(inv.supplier_id),
            state.as_of,
            ow,
            bank_facility,
            supplier_facility,
            shortfall_at_binding,
        )
        for inv in state.invoices
    }

    method = "GREEDY_FALLBACK"
    status = "FEASIBLE"
    fallback_used = True
    n_scenarios = 1
    allocation = None

    remaining = SOLVE_BUDGET_S - (time.monotonic() - t0)
    if candidates_by_invoice and remaining > 0.3:
        result = milp.solve(candidates_by_invoice, mc.min_per_path, state.facilities)
        if result is not None:
            allocation, n_scenarios = result
            method, status, fallback_used = "MILP_SCENARIO", "OPTIMAL", False

    if allocation is None:
        allocation = greedy_fallback.solve(candidates_by_invoice, fc.deployable_cash, state.facilities)
        status = "TIMEOUT" if remaining <= 0.3 and candidates_by_invoice else "FEASIBLE"

    actions: list[Action] = []
    for i, (invoice_id, chosen) in enumerate(allocation.chosen.items(), start=1):
        others = allocation.rejected.get(invoice_id, [])
        rejected_alts = [
            RejectedAlternative(
                action=o.action,
                net_value=o.net_value,
                delta=min(0.0, round(o.net_value - chosen.net_value, 2)),
                reason_code=candidates_mod.rejection_reason(o, chosen),
            )
            for o in others
        ] or [
            RejectedAlternative(action=chosen.action, net_value=chosen.net_value, delta=0.0, reason_code="NO_BETTER_ALTERNATIVE")
        ]

        actions.append(
            Action(
                action_id=f"ACT-{i:04d}",
                target_type="INVOICE",
                target_id=invoice_id,
                supplier_id=chosen.supplier.id if chosen.supplier else None,
                action=chosen.action,
                amount=chosen.amount,
                execute_on=chosen.execute_on,
                funding_source=chosen.funding_source,
                facility_id=chosen.facility.id if chosen.facility else None,
                confidence=_confidence(chosen.score, [c.score for c in candidates_by_invoice[invoice_id]]),
                score_breakdown=ScoreBreakdown(
                    discount_captured=chosen.discount_captured,
                    penalty_incurred=chosen.penalty_incurred,
                    financing_cost=chosen.financing_cost,
                    liquidity_risk_cost=chosen.liquidity_risk_cost,
                    supplier_stress_delta=chosen.supplier_stress_delta,
                    net_value=chosen.net_value,
                ),
                binding_constraints=chosen.binding_constraints,
                primary_reason_code=chosen.primary_reason_code,
                rejected_alternatives=rejected_alts,
                status="PROPOSED",
            )
        )

    diff = decision_diff.compute(previous_dict, allocation.chosen)

    return DecisionObject(
        decision_id="DEC-000000",  # simulation fact — every caller overwrites this
        run_at=state.as_of,
        sim_day=state.sim_day,
        policy="AGENT",
        trigger=_resolve_trigger(trigger),
        cash_before=state.cash_available,
        buffer_required=fc.buffer_required,
        deployable_cash=fc.deployable_cash,
        objective_weights=ow,
        objective_value=round(sum(c.score for c in allocation.chosen.values()), 2),
        actions=actions,
        facility_actions=_facility_actions(allocation.chosen, state.as_of, state.facilities),
        solver=SolverInfo(
            method=method,
            status=status,
            solve_ms=int((time.monotonic() - t0) * 1000),
            n_scenarios=n_scenarios,
            fallback_used=fallback_used,
        ),
        diff_from_previous=DiffFromPrevious(**diff),
        explanation=None,
    )


# `python -m engine.decide --state contracts/fixtures/state.sample.json` — FINAL.md §12's own
# H+12 checkpoint: "print a valid DecisionObject with populated rejected_alternatives."
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--forecast-only", action="store_true")
    args = parser.parse_args()

    loaded_state = State.model_validate(json.loads(open(args.state, encoding="utf-8").read()))
    if args.forecast_only:
        print(forecast(loaded_state).model_dump_json(indent=2, by_alias=True))
    else:
        print(decide(loaded_state).model_dump_json(indent=2, by_alias=True))
