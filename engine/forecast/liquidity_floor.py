# engine/forecast/liquidity_floor.py — FINAL.md §11.5's central claim:
# deployable_cash = max(0, P_alpha(min-over-horizon cash)). Any rupee spent discretionarily
# today reduces every future daily balance by exactly one rupee, so the largest amount
# spendable today while keeping the alpha-percentile worst future balance at or above zero
# is precisely that percentile (see FINAL.md §11.5 for the full argument).
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np

from contracts.schemas import State
from engine.forecast.monte_carlo import MonteCarloResult, bucket_date


@dataclass
class LiquidityFloor:
    deployable_cash: float
    buffer_required: float
    binding_date: date | None
    binding_reason: str | None
    worst_case_min_cash: float


def compute(state: State, mc: MonteCarloResult, alpha: float, horizon_days: int) -> LiquidityFloor:
    min_per_path = mc.min_per_path
    q = float(np.percentile(min_per_path, alpha * 100))
    deployable_cash = max(0.0, q)
    buffer_required = max(0.0, state.cash_available - deployable_cash)
    worst_case_min_cash = float(min_per_path.min())

    if min_per_path.size == 0:
        return LiquidityFloor(deployable_cash, buffer_required, None, None, worst_case_min_cash)

    # The path whose worst point lands closest to the alpha percentile — the representative
    # "5th percentile scenario" the narrative talks about, not literally the single worst path.
    worst_idx = int(np.argmin(np.abs(min_per_path - q)))
    day_of_min = int(np.argmin(mc.balances[worst_idx]))
    binding_date = bucket_date(state.as_of, day_of_min)

    # Name the largest committed outflow on or within 2 days of the trough day.
    window = range(max(0, day_of_min - 2), min(horizon_days, day_of_min + 2) + 1)
    best_obligation = None
    for o in state.obligations:
        offset = (o.due_date - state.as_of).days
        if offset in window and (best_obligation is None or o.amount > best_obligation.amount):
            best_obligation = o

    # The receivable that arrived latest (relative to its own expectation), among those that
    # had arrived by the trough day in this specific simulated path.
    latest_id: str | None = None
    latest_delay = -1
    for j, rid in enumerate(mc.receivable_ids):
        arrival = int(mc.arrival_days[worst_idx, j])
        if arrival <= day_of_min:
            delay = arrival - int(mc.expected_offsets[j])
            if delay > latest_delay:
                latest_delay = delay
                latest_id = rid

    parts: list[str] = []
    if best_obligation is not None:
        parts.append(best_obligation.label)
    if latest_id is not None and latest_delay > 0:
        parts.append(f"with {latest_id} collecting {latest_delay}d late in the 5th percentile path")
    binding_reason = ", ".join(parts) if parts else "liquidity floor reached with no single dominant cause"

    return LiquidityFloor(deployable_cash, buffer_required, binding_date, binding_reason, worst_case_min_cash)
