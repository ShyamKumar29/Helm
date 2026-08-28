# api/seed/planted.py — B2. The three demo situations, written by hand.
#
# docs/backend/05-PHASE-B2-seed-data.md step 3: "Do not hope the random draw produces them.
# Write them explicitly ... and overwrite whatever the generator produced for those specific
# IDs." Applied last, after build_world(), so this always wins — 13-SEED-DATA-SPEC.md section
# 10 rule 6.
#
# Also fixes the six demo-critical IDs (task spec) so a regenerate can never shuffle them out
# from under the frontend's hardcoded chaos-panel presets:
#   RCV-0004, FAC-001, SUP-001, INV-0001, OBL-001, CUS-004
from __future__ import annotations

from datetime import date


def _find(rows: list[dict], id_: str) -> dict:
    for r in rows:
        if r["id"] == id_:
            return r
    raise KeyError(
        f"planted.py expected id {id_!r} to already exist from build_world()"
    )


def apply(world: dict) -> dict:
    start_date: date = world["start_date"]

    # ---------------------------------------------------------------------------------
    # SITUATION 1 — borrow to take the discount. Demo script 3:00, the why-not panel.
    # INV-0001 on SUP-001 (Meenakshi Steels), 2/10 net 30 (37.2% implied APR of forgoing)
    # against FAC-001 at 13.5%. discount_until falls in the first week of the sim, and the
    # amount is sized so paying from cash breaches the liquidity floor once the buffer
    # requirement (situation 2) is netted out — the agent must borrow to capture it.
    # ---------------------------------------------------------------------------------
    sup1 = _find(world["suppliers"], "SUP-001")
    sup1.update(
        name="Meenakshi Steels",
        criticality=0.90,
        liquidity_stress=0.35,
        supplier_finance_eligible=True,
    )
    fac2 = _find(world["facilities"], "FAC-002")
    if sup1["id"] not in (fac2["eligible_supplier_ids"] or []):
        fac2["eligible_supplier_ids"].append(sup1["id"])

    inv1 = _find(world["invoices"], "INV-0001")
    discount_until = date(2026, 3, 5)  # first week of the sim (sim_day 4)
    issue_date = date(2026, 2, 23)  # discount_until - 10 days (2/10 net 30)
    inv1.update(
        supplier_id="SUP-001",
        amount=850_000.0,
        issue_date=issue_date,
        due_date=date(2026, 3, 25),  # issue_date + 30
        discount_pct=2.0,
        discount_until=discount_until,
        penalty_bps_per_day=5.0,
        max_delay_days=15,
        status="OPEN",
    )

    # ---------------------------------------------------------------------------------
    # SITUATION 2 — cash-rich but not really. Demo script 0:30 and 1:00; chaos preset #1
    # amplifies this directly. RCV-0004 is the largest receivable, on the worst-paying
    # customer (CUS-004, Ashwin Motors, mean_delay 18d / std 9d / on_time 15%), collecting
    # 3-5 days before OBL-001 payroll (2026-03-31, fixed below). Delaying it in the chaos
    # panel pushes collection past payroll and the forecast's P5 min cash goes negative.
    # ---------------------------------------------------------------------------------
    cus4 = _find(world["customers"], "CUS-004")
    cus4.update(name="Ashwin Motors")

    rcv4 = _find(world["receivables"], "RCV-0004")
    rcv4.update(
        customer_id="CUS-004",
        amount=4_200_000.0,
        expected_date=date(2026, 3, 27),  # 4 days before month-end payroll
        status="OPEN",
    )

    obl1 = _find(world["obligations"], "OBL-001")
    obl1.update(
        label="Payroll March 2026",
        category="PAYROLL",
        amount=2_200_000.0,
        due_date=date(2026, 3, 31),
        hard=True,
    )

    # ---------------------------------------------------------------------------------
    # SITUATION 3 — the stressed critical supplier. Demo script 4:00, the supplier-stress
    # weight slider. SUP-002 is highly critical and already under liquidity stress at seed
    # time (unlike SUP-001, whose stress is raised at runtime by chaos preset #4) — a
    # pure-cost optimiser would delay its small invoice; the supplier-stress objective term
    # pays it anyway. INV-0002 is that invoice: modest, no discount, due in the same tight
    # cash week as payroll.
    # ---------------------------------------------------------------------------------
    sup2 = _find(world["suppliers"], "SUP-002")
    sup2.update(
        name="Karthik Polymers",
        criticality=0.88,
        liquidity_stress=0.80,
        supplier_finance_eligible=sup2["supplier_finance_eligible"],
    )

    inv2 = _find(world["invoices"], "INV-0002")
    inv2.update(
        supplier_id="SUP-002",
        amount=225_000.0,
        issue_date=date(2026, 3, 5),
        due_date=date(2026, 3, 29),  # tight cash week, same week as payroll
        discount_pct=None,
        discount_until=None,
        penalty_bps_per_day=4.0,
        max_delay_days=10,
        status="OPEN",
    )

    # ---------------------------------------------------------------------------------
    # Demo-critical facilities — fully fixed already by build_world(), restated here so a
    # future edit to the generator can never silently drift them.
    # ---------------------------------------------------------------------------------
    fac1 = _find(world["facilities"], "FAC-001")
    fac1.update(
        type="BANK_LINE",
        limit_amount=5_000_000.0,
        apr_pct=13.5,
        min_draw=50_000.0,
        repayment_days=60,
        eligible_supplier_ids=None,
    )

    assert start_date == date(2026, 3, 1), (
        "planted dates assume SIM_START_DATE=2026-03-01"
    )
    return world
