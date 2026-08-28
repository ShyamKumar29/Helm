# engine/rng.py — deterministic seeding (CLAUDE.md rule 6: "the same state must produce
# the same decision every time, or the demo flickers").
#
# The spec phrase is "seed from (sim_day, decision_id)" — but decision_id doesn't exist yet
# when decide()/forecast() run (api/ stamps it onto the result afterward, per FINAL.md §12's
# own build-order notes and every caller in api/routers/decisions.py, events.py,
# api/services/sim_loop.py). The thing that actually needs to be reproducible is "same
# State in, same answer out" — so this seeds off a stable digest of the State content itself
# (which sim_day is already part of) instead. Two calls with byte-identical State always
# produce the same seed, and therefore the same Monte Carlo paths and the same decision.
from __future__ import annotations

import hashlib

import numpy as np

from contracts.schemas import State


def state_seed(state: State) -> int:
    """A deterministic 63-bit seed derived from everything in State that can change the
    answer — sim_day/as_of, cash, and every receivable/invoice/obligation/facility id and
    amount. Field order is fixed (Pydantic preserves declaration order), so this is stable
    across processes and re-runs, which is the whole point."""
    parts: list[str] = [
        str(state.sim_day),
        state.as_of.isoformat(),
        f"{state.cash_available:.2f}",
    ]
    for r in state.receivables:
        parts.append(f"{r.id}:{r.amount:.2f}:{r.expected_date.isoformat()}:{r.status}")
    for i in state.invoices:
        parts.append(f"{i.id}:{i.amount:.2f}:{i.due_date.isoformat()}:{i.status}")
    for o in state.obligations:
        parts.append(f"{o.id}:{o.amount:.2f}:{o.due_date.isoformat()}")
    for f in state.facilities:
        parts.append(f"{f.id}:{f.drawn:.2f}:{f.apr_pct}")

    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    # Top 8 bytes as an unsigned int, masked into numpy's 63-bit Generator seed range.
    return int.from_bytes(digest[:8], "big") & 0x7FFFFFFFFFFFFFFF


def rng_for(state: State) -> np.random.Generator:
    return np.random.default_rng(state_seed(state))
