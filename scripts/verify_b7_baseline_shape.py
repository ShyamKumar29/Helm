#!/usr/bin/env python
"""scripts/verify_b7_baseline_shape.py — validates api/baseline/static_rules.py's action
shapes against contracts/schemas.py without a database. Exercises `_action()` directly for
each of the four branches (FINAL.md section 11.8), then assembles and validates a full
`DecisionObject` the same way api/services/sim_loop.py step 7 does, using an in-memory fake
in place of `run()`'s DB queries.

The DB-backed parts of api/baseline/static_rules.py.run() (open-invoice query, bank facility
lookup, previous-decision lookup) need Postgres and are not exercised here — see the B7
handoff report for what remains unverified in this environment.

Run with the repo's venv Python from the repo root:  python scripts/verify_b7_baseline_shape.py
"""

from types import SimpleNamespace

from api.baseline import static_rules
from contracts.schemas import Action, DecisionObject

failures = []


def check(name, condition):
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        failures.append(name)


inv = SimpleNamespace(
    id="INV-0001",
    supplier_id="SUP-001",
    amount=850000.0,
    discount_pct=2.0,
    discount_until="2026-03-02",
    due_date="2026-03-22",
)

# ---- each of the four branches produces a schema-valid Action -----------------------------

pay_early = static_rules._action(
    1,
    inv,
    "PAY_EARLY_DISCOUNT",
    833000.0,
    "2026-03-14",
    "CASH",
    None,
    "DISCOUNT_CAPTURED",
    "PAY_AT_MATURITY",
    "NO_BETTER_ALTERNATIVE",
    discount_captured=17000.0,
)
pay_maturity = static_rules._action(
    2,
    inv,
    "PAY_AT_MATURITY",
    850000.0,
    "2026-03-14",
    "CASH",
    None,
    "PENALTY_AVOIDED",
    "FINANCE_BANK",
    "NO_BETTER_ALTERNATIVE",
)
finance_bank = static_rules._action(
    3,
    inv,
    "FINANCE_BANK",
    850000.0,
    "2026-03-14",
    "BANK_LINE",
    "FAC-001",
    "INSUFFICIENT_CASH",
    "PAY_AT_MATURITY",
    "INSUFFICIENT_CASH",
)
hold = static_rules._action(
    4,
    inv,
    "HOLD",
    850000.0,
    None,
    "CASH",
    None,
    "NO_BETTER_ALTERNATIVE",
    "PAY_NOW",
    "NO_BETTER_ALTERNATIVE",
)

for label, action_dict in [
    ("PAY_EARLY_DISCOUNT", pay_early),
    ("PAY_AT_MATURITY", pay_maturity),
    ("FINANCE_BANK", finance_bank),
    ("HOLD", hold),
]:
    try:
        Action.model_validate(action_dict)
        check(f"{label} action validates against contracts.schemas.Action", True)
    except Exception as e:
        check(f"{label} action validates against contracts.schemas.Action ({e})", False)

check(
    "PS requirement 7: every action has >= 1 rejected_alternatives",
    all(
        len(a["rejected_alternatives"]) >= 1
        for a in [pay_early, pay_maturity, finance_bank, hold]
    ),
)
check(
    "every rejected_alternatives[].delta <= 0",
    all(
        alt["delta"] <= 0
        for a in [pay_early, pay_maturity, finance_bank, hold]
        for alt in a["rejected_alternatives"]
    ),
)
check(
    "CASH funding implies facility_id is null",
    all(
        a["facility_id"] is None
        for a in [pay_early, pay_maturity, hold]
        if a["funding_source"] == "CASH"
    ),
)
check(
    "BANK_LINE funding carries a facility_id",
    finance_bank["funding_source"] == "BANK_LINE"
    and finance_bank["facility_id"] is not None,
)

# ---- a full DecisionObject, stamped the way sim_loop.step_7_run_baseline stamps it --------

decision_dict = {
    "trigger": {
        "type": "SCHEDULED",
        "event_id": None,
        "materiality_score": None,
        "description": "baseline daily rule run",
    },
    "cash_before": 4200000.0,
    "buffer_required": 500000.0,
    "deployable_cash": 3700000.0,
    "objective_weights": static_rules.ZERO_WEIGHTS,
    "objective_value": 0.0,
    "actions": [pay_early, pay_maturity, finance_bank, hold],
    "facility_actions": [],
    "solver": {
        "method": "GREEDY_FALLBACK",
        "status": "FEASIBLE",
        "solve_ms": 0,
        "n_scenarios": 0,
        "fallback_used": False,
    },
    "diff_from_previous": {
        "previous_decision_id": None,
        "flipped": [],
        "added": [],
        "removed": [],
    },
    "explanation": None,
    # stamped by sim_loop.step_7_run_baseline immediately before validation:
    "decision_id": "DEC-000001",
    "run_at": "2026-03-13",
    "sim_day": 12,
    "policy": "BASELINE",
}

try:
    DecisionObject.model_validate(decision_dict)
    check(
        "full baseline DecisionObject validates against contracts.schemas.DecisionObject",
        True,
    )
except Exception as e:
    check(
        f"full baseline DecisionObject validates against contracts.schemas.DecisionObject ({e})",
        False,
    )

print(f"  ---- {len(failures)} failed")
if failures:
    raise SystemExit(1)
