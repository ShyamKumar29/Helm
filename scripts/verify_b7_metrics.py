#!/usr/bin/env python
"""scripts/verify_b7_metrics.py — B7 formula checks that need no DB and no pytest, matching
the project's own testing philosophy (docs/backend/14-TESTING-AND-VERIFICATION.md: "Not a
test suite. A set of gates."). Run with the repo's venv Python from the repo root:

    python scripts/verify_b7_metrics.py

Covers api/services/metrics.py's pure functions only (health_score, net_working_capital_cost,
savings_per_day, compute_delta) — the DB-backed aggregation queries need Postgres and are
exercised instead by docs/backend/10-PHASE-B7-baseline-and-metrics.md section 7's curl+python
verify script and docs/backend/14's scripts/replay_check.py, neither of which can run in this
environment (no docker/Postgres available here — see the B7 handoff report).
"""

from api.services import metrics

failures = []


def check(name, condition):
    if condition:
        print(f"  ok   {name}")
    else:
        print(f"  FAIL {name}")
        failures.append(name)


# --------------------------------------------------------------------------------------
# net_working_capital_cost — FINAL.md section 8.7 / 12-API-CONTRACT-CHECKLIST.md §3:
# "financing_cost + penalties_paid - discounts_captured", exactly.
# --------------------------------------------------------------------------------------
check(
    "nwc = financing_cost + penalties_paid - discounts_captured",
    metrics.net_working_capital_cost(62400.0, 8400.0, 184000.0) == -113200.0,
)
check(
    "nwc matches the frozen compare.sample.json baseline row",
    metrics.net_working_capital_cost(118900.0, 47600.0, 41000.0) == 125500.0,
)

# --------------------------------------------------------------------------------------
# savings_per_day — "-net_working_capital_cost / max(sim_day, 1)"
# --------------------------------------------------------------------------------------
check(
    "savings_per_day matches the frozen fixture (agent, sim_day 45)",
    metrics.savings_per_day(-113200.0, 45) == round(113200.0 / 45, 2),
)
check(
    "savings_per_day never divides by zero at sim_day 0",
    metrics.savings_per_day(-500.0, 0) == 500.0,
)

# --------------------------------------------------------------------------------------
# health_score — FINAL.md section 8.7 / B7 doc §4, verbatim formula.
# --------------------------------------------------------------------------------------
common = dict(
    shortfall_days=0,
    obligations_missed=0,
    penalties_paid=8400.0,
    discounts_captured=184000.0,
    avg_supplier_stress=0.31,
    financing_cost=62400.0,
    total_obligations=42,
    total_payable_value=60_000_000.0,
    total_discount_available=200_000.0,
)
check(
    "health_score is an int in [0, 100]",
    isinstance(metrics.health_score(sim_day=45, **common), int)
    and 0 <= metrics.health_score(sim_day=45, **common) <= 100,
)
check(
    "health_score never divides by zero at sim_day 0 (the bug the doc calls out)",
    metrics.health_score(sim_day=0, **common)
    == metrics.health_score(sim_day=0, **common),
)
zero_world = dict(
    common, total_obligations=0, total_payable_value=0.0, total_discount_available=0.0
)
check(
    "health_score never divides by zero on an empty world (0 obligations/payables/discounts)",
    0 <= metrics.health_score(sim_day=1, **zero_world) <= 100,
)
check(
    "health_score clamps to 100 when nothing at all went wrong",
    metrics.health_score(
        shortfall_days=0,
        obligations_missed=0,
        penalties_paid=0.0,
        discounts_captured=200_000.0,
        avg_supplier_stress=0.0,
        financing_cost=0.0,
        sim_day=10,
        total_obligations=10,
        total_payable_value=1_000_000.0,
        total_discount_available=200_000.0,
    )
    == 100,
)
check(
    "health_score clamps to 0 rather than going negative under a catastrophic policy",
    metrics.health_score(
        shortfall_days=1000,
        obligations_missed=1000,
        penalties_paid=10_000_000.0,
        discounts_captured=0.0,
        avg_supplier_stress=1.0,
        financing_cost=10_000_000.0,
        sim_day=10,
        total_obligations=1,
        total_payable_value=1.0,
        total_discount_available=1.0,
    )
    == 0,
)

# --------------------------------------------------------------------------------------
# compute_delta — always agent - baseline (FINAL.md fixture: 82 - 41 = 41).
# --------------------------------------------------------------------------------------
agent = {
    "net_working_capital_cost": -113200.0,
    "shortfall_days": 0,
    "obligations_missed": 0,
    "health_score": 82,
}
baseline = {
    "net_working_capital_cost": 125500.0,
    "shortfall_days": 3,
    "obligations_missed": 1,
    "health_score": 41,
}
d = metrics.compute_delta(agent, baseline)
check(
    "delta.net_working_capital_cost matches the frozen fixture",
    d["net_working_capital_cost"] == -238700.0,
)
check("delta.shortfall_days matches the frozen fixture", d["shortfall_days"] == -3)
check(
    "delta.obligations_missed matches the frozen fixture", d["obligations_missed"] == -1
)
check(
    "delta.health_score matches the frozen fixture (82 - 41 = 41)",
    d["health_score"] == 41,
)

print(f"  ---- {len(failures)} failed")
if failures:
    raise SystemExit(1)
