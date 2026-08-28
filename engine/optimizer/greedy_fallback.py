# engine/optimizer/greedy_fallback.py — FINAL.md §12 build order step 3: "pick the best
# action per invoice greedily under the deployable_cash constraint, sorted by net value per
# rupee of cash consumed. That greedy version is your fallback and it must survive to the
# end. Do not delete it when the MILP works." This is the permanent floor everything else
# (milp.py, and engine_gateway.py's own timeout) degrades to.
from __future__ import annotations

from dataclasses import dataclass

from contracts.schemas import Facility
from engine.actions.candidates import Candidate


@dataclass
class Allocation:
    chosen: dict[str, Candidate]  # invoice_id -> chosen Candidate
    rejected: dict[str, list[Candidate]]  # invoice_id -> every other candidate, in score order


def _density(candidates: list[Candidate]) -> float:
    best = max(candidates, key=lambda c: c.score)
    return best.score / max(best.amount, 1.0)


def solve(
    candidates_by_invoice: dict[str, list[Candidate]],
    deployable_cash: float,
    facilities: list[Facility],
) -> Allocation:
    cash_used = 0.0
    facility_drawn: dict[str, float] = {f.id: 0.0 for f in facilities}
    facility_by_id = {f.id: f for f in facilities}

    order = sorted(candidates_by_invoice.items(), key=lambda kv: _density(kv[1]), reverse=True)

    chosen: dict[str, Candidate] = {}
    rejected: dict[str, list[Candidate]] = {}

    for invoice_id, candidates in order:
        ranked = sorted(candidates, key=lambda c: c.score, reverse=True)
        pick: Candidate | None = None
        for c in ranked:
            if c.funding_source == "CASH":
                if cash_used + c.amount <= deployable_cash + 1e-6:
                    pick = c
                    break
            elif c.facility is not None:
                fac = facility_by_id[c.facility.id]
                if facility_drawn[fac.id] + fac.drawn + c.amount <= fac.limit + 1e-6:
                    pick = c
                    break
            else:  # HOLD — amount is always 0, always affordable
                pick = c
                break

        if pick is None:
            # Every priced option is over budget — HOLD (amount 0) is always in the list and
            # always affordable, so this is unreachable in practice; kept as an explicit,
            # provably-safe fallback rather than trusting that invariant silently.
            pick = next(c for c in candidates if c.action == "HOLD")

        if pick.funding_source == "CASH":
            cash_used += pick.amount
        elif pick.facility is not None:
            facility_drawn[pick.facility.id] += pick.amount

        chosen[invoice_id] = pick
        rejected[invoice_id] = [c for c in candidates if c is not pick]

    return Allocation(chosen=chosen, rejected=rejected)
