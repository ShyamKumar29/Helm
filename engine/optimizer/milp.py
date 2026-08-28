# engine/optimizer/milp.py — FINAL.md §12 build order step "H+12-H+16 — the optimiser":
# a scenario-based MILP over PuLP/CBC. Binary x[invoice, candidate] with one selected per
# invoice; the liquidity constraint is applied per scenario (5 percentiles of the Monte Carlo
# minimum-cash-per-path distribution), so the chosen plan has to survive every one of them,
# not just the expected case — facility limits are applied globally. Hard time-limited; any
# failure (infeasible, timeout, PuLP missing, CBC missing) returns `None` and
# `engine/decide.py` falls back to `greedy_fallback.py`, which "must survive to the end."
from __future__ import annotations

import logging

import numpy as np

from contracts.schemas import Facility
from engine.actions.candidates import Candidate
from engine.optimizer.greedy_fallback import Allocation

log = logging.getLogger(__name__)

SOLVE_TIME_LIMIT_S = 1.0  # engine's own internal budget stays under the 2s hard cap, and
# under docs/backend/11-PHASE-B8-hardening-and-demo.md's `POST /decide < 2.5s` end-to-end
# performance budget once forecast/candidate-generation/API overhead is added on top
# FINAL.md §12: "cluster the 2000 Monte Carlo paths into 5 representative scenarios ... the
# percentile approach is simpler, faster and perfectly defensible."
SCENARIO_PERCENTILES = (10, 30, 50, 70, 90)


def solve(
    candidates_by_invoice: dict[str, list[Candidate]],
    min_cash_per_path: np.ndarray,
    facilities: list[Facility],
) -> tuple[Allocation, int] | None:
    """Returns (allocation, n_scenarios) on a real optimal/feasible solve, `None` on anything
    else — infeasible, timeout, or PuLP/CBC not available."""
    try:
        import pulp
    except Exception:
        log.info("pulp not importable, milp unavailable")
        return None

    if min_cash_per_path.size == 0:
        scenario_budgets = [0.0]
    else:
        scenario_budgets = [
            max(0.0, float(np.percentile(min_cash_per_path, p))) for p in SCENARIO_PERCENTILES
        ]

    prob = pulp.LpProblem("helm_decision", pulp.LpMaximize)

    x: dict[tuple[str, int], pulp.LpVariable] = {}
    for invoice_id, candidates in candidates_by_invoice.items():
        for idx, _c in enumerate(candidates):
            x[(invoice_id, idx)] = pulp.LpVariable(f"x_{invoice_id}_{idx}", cat="Binary")

    # exactly one action per invoice
    for invoice_id, candidates in candidates_by_invoice.items():
        prob += pulp.lpSum(x[(invoice_id, idx)] for idx in range(len(candidates))) == 1

    # liquidity: cash spent must fit inside every one of the 5 scenario budgets
    cash_terms = [
        (x[(invoice_id, idx)], c.amount)
        for invoice_id, candidates in candidates_by_invoice.items()
        for idx, c in enumerate(candidates)
        if c.funding_source == "CASH"
    ]
    for budget in scenario_budgets:
        prob += pulp.lpSum(var * amount for var, amount in cash_terms) <= budget

    # facility limits: global, one constraint per facility
    for facility in facilities:
        terms = [
            (x[(invoice_id, idx)], c.amount)
            for invoice_id, candidates in candidates_by_invoice.items()
            for idx, c in enumerate(candidates)
            if c.facility is not None and c.facility.id == facility.id
        ]
        if terms:
            prob += pulp.lpSum(var * amount for var, amount in terms) <= facility.limit - facility.drawn

    # objective — the weighted score already folds in the expectation (liquidity_risk_cost is
    # itself derived from the Monte Carlo shortfall probability); the scenario constraints
    # above are what makes this a scenario MILP rather than a single deterministic LP.
    prob += pulp.lpSum(
        x[(invoice_id, idx)] * c.score
        for invoice_id, candidates in candidates_by_invoice.items()
        for idx, c in enumerate(candidates)
    )

    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=SOLVE_TIME_LIMIT_S)
    try:
        prob.solve(solver)
    except Exception:
        log.exception("CBC solve raised")
        return None

    status = pulp.LpStatus[prob.status]
    if status != "Optimal":
        log.info("milp solve ended %s, falling back to greedy", status)
        return None

    chosen: dict[str, Candidate] = {}
    rejected: dict[str, list[Candidate]] = {}
    for invoice_id, candidates in candidates_by_invoice.items():
        picked_idx = None
        for idx in range(len(candidates)):
            val = x[(invoice_id, idx)].value()
            if val is not None and val > 0.5:
                picked_idx = idx
                break
        if picked_idx is None:
            # CBC returned Optimal but somehow left an invoice unassigned (numerical
            # tolerance) — HOLD is always present and always feasible.
            picked_idx = next(i for i, c in enumerate(candidates) if c.action == "HOLD")
        chosen[invoice_id] = candidates[picked_idx]
        rejected[invoice_id] = [c for i, c in enumerate(candidates) if i != picked_idx]

    return Allocation(chosen=chosen, rejected=rejected), len(scenario_budgets)
