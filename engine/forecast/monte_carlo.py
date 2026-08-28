# engine/forecast/monte_carlo.py — FINAL.md §11.5, vectorized (numpy, no per-path Python
# loop — that's what the 400ms budget forbids).
#
# `committed_out` (the non-discretionary side of the ledger) is built from `state.obligations`
# only. FINAL.md's pseudocode also lists "invoices_already_scheduled" and
# "facility_repayments", but neither is representable from the frozen `State` contract as it
# stands today: `State.invoices` carries no execution date (that lives on an `Action`, not an
# `Invoice`), and `State.facilities` carries only an aggregate `drawn` total, not per-draw
# repayment dates. Committed obligations are the genuinely non-negotiable side of the ledger
# (payroll, tax, rent, EMI); invoices are exactly the discretionary spend `decide()` is being
# asked to allocate, which is why leaving them out of `committed_out` is consistent with
# `deployable_cash`'s own definition (§11.5) rather than a shortcut around it.
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from contracts.schemas import State
from engine.forecast.delay_models import sample_delays


@dataclass
class MonteCarloResult:
    balances: np.ndarray  # (n_paths, horizon+1)
    p10: np.ndarray
    p50: np.ndarray
    p90: np.ndarray
    shortfall_prob: np.ndarray
    cum_committed: np.ndarray  # (horizon+1,) — same for every path
    cum_expected_inflow: np.ndarray  # (horizon+1,) — P50 across paths
    min_per_path: np.ndarray  # (n_paths,)
    receivable_ids: list[str]
    expected_offsets: np.ndarray  # (n_receivables,)
    arrival_days: np.ndarray  # (n_paths, n_receivables)


def _committed_outflow_schedule(state: State, horizon_days: int) -> np.ndarray:
    schedule = np.zeros(horizon_days + 1)
    for o in state.obligations:
        offset = (o.due_date - state.as_of).days
        if 0 <= offset <= horizon_days:
            schedule[offset] += float(o.amount)
    return schedule


def run(
    state: State,
    horizon_days: int,
    n_paths: int,
    rng: np.random.Generator,
) -> MonteCarloResult:
    customers_by_id = {c.id: c for c in state.customers}
    receivables = state.receivables
    n_r = len(receivables)

    committed = _committed_outflow_schedule(state, horizon_days)
    cum_committed = np.cumsum(committed)

    daily_inflow = np.zeros((n_paths, horizon_days + 1))
    expected_offsets = np.zeros(n_r, dtype=int)
    arrival_days = np.zeros((n_paths, n_r), dtype=int)

    for j, r in enumerate(receivables):
        expected_offset = (r.expected_date - state.as_of).days
        expected_offsets[j] = expected_offset
        delays = sample_delays(rng, customers_by_id.get(r.customer_id), n_paths)
        arrival = np.maximum(0, expected_offset + delays.astype(int))
        arrival_days[:, j] = arrival

        in_window = arrival <= horizon_days
        if not np.any(in_window):
            continue
        path_idx = np.nonzero(in_window)[0]
        np.add.at(daily_inflow, (path_idx, arrival[in_window]), float(r.amount))

    cum_inflow = np.cumsum(daily_inflow, axis=1)
    balances = state.cash_available + cum_inflow - cum_committed[None, :]

    return MonteCarloResult(
        balances=balances,
        p10=np.percentile(balances, 10, axis=0),
        p50=np.percentile(balances, 50, axis=0),
        p90=np.percentile(balances, 90, axis=0),
        shortfall_prob=(balances < 0).mean(axis=0),
        cum_committed=cum_committed,
        cum_expected_inflow=np.percentile(cum_inflow, 50, axis=0),
        min_per_path=balances.min(axis=1),
        receivable_ids=[r.id for r in receivables],
        expected_offsets=expected_offsets,
        arrival_days=arrival_days,
    )


def bucket_date(as_of: date, offset: int) -> date:
    return as_of + timedelta(days=offset)
