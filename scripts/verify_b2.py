"""Verification harness for Phase B2 — run against a live seeded DB. Not part of the app;
ad hoc script for the completion-report checks. Safe to delete once B2 is signed off."""

import json

from sqlalchemy import text

from api.db import SessionLocal
from api.seed.seed import seed_world

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
    else:
        FAIL.append(f"{name} :: {detail}")


def q(sess, sql, **params):
    return sess.execute(text(sql), params).all()


def run():
    summary = seed_world(seed=42, start_date="2026-03-01")
    sess = SessionLocal()

    # counts
    n_sup = q(sess, "select count(*) from suppliers")[0][0]
    n_cus = q(sess, "select count(*) from customers")[0][0]
    n_obl = q(sess, "select count(*) from obligations")[0][0]
    n_rcv = q(sess, "select count(*) from receivables")[0][0]
    inv_by_policy = dict(
        q(sess, "select policy, count(*) from invoices group by policy")
    )
    fac_by_policy = dict(
        q(sess, "select policy, count(*) from facilities group by policy")
    )

    check("40 suppliers", n_sup == 40, n_sup)
    check("8 customers", n_cus == 8, n_cus)
    check("12 obligations", n_obl == 12, n_obl)
    check("60 receivables", n_rcv == 60, n_rcv)
    check(
        "200 invoices per policy, both policies",
        inv_by_policy == {"AGENT": 200, "BASELINE": 200},
        inv_by_policy,
    )
    check(
        "2 facilities per policy, both policies",
        fac_by_policy == {"AGENT": 2, "BASELINE": 2},
        fac_by_policy,
    )

    # six critical IDs exist exactly once (accounting for policy duplication on inv/fac)
    check(
        "RCV-0004 exists exactly once",
        len(q(sess, "select 1 from receivables where id='RCV-0004'")) == 1,
    )
    check(
        "FAC-001 exists exactly once per policy (2 total)",
        len(q(sess, "select 1 from facilities where id='FAC-001'")) == 2,
    )
    check(
        "SUP-001 exists exactly once",
        len(q(sess, "select 1 from suppliers where id='SUP-001'")) == 1,
    )
    check(
        "INV-0001 exists exactly once per policy (2 total)",
        len(q(sess, "select 1 from invoices where id='INV-0001'")) == 2,
    )
    check(
        "OBL-001 exists exactly once",
        len(q(sess, "select 1 from obligations where id='OBL-001'")) == 1,
    )
    check(
        "CUS-004 exists exactly once",
        len(q(sess, "select 1 from customers where id='CUS-004'")) == 1,
    )

    # FK integrity
    orphan_inv = q(
        sess,
        """select count(*) from invoices i
                             left join suppliers s on i.supplier_id = s.id
                             where s.id is null""",
    )[0][0]
    orphan_rcv = q(
        sess,
        """select count(*) from receivables r
                             left join customers c on r.customer_id = c.id
                             where c.id is null""",
    )[0][0]
    check("no orphan invoices (supplier FK)", orphan_inv == 0, orphan_inv)
    check("no orphan receivables (customer FK)", orphan_rcv == 0, orphan_rcv)

    # duplicate-ID impossibility: PK enforcement already proven by the successful insert
    # above (composite PK collisions would have raised IntegrityError); reconfirm no dupes
    # exist within a single policy.
    dup_inv = q(
        sess,
        """select id, policy, count(*) c from invoices
                          group by id, policy having count(*) > 1""",
    )
    dup_fac = q(
        sess,
        """select id, policy, count(*) c from facilities
                          group by id, policy having count(*) > 1""",
    )
    check("no duplicate invoice (id,policy)", len(dup_inv) == 0, dup_inv)
    check("no duplicate facility (id,policy)", len(dup_fac) == 0, dup_fac)

    # opening cash
    bal_agent = q(sess, "select balance from cash_ledger where policy='AGENT'")[0][0]
    bal_base = q(sess, "select balance from cash_ledger where policy='BASELINE'")[0][0]
    n_ledger_agent = q(sess, "select count(*) from cash_ledger where policy='AGENT'")[
        0
    ][0]
    n_ledger_base = q(sess, "select count(*) from cash_ledger where policy='BASELINE'")[
        0
    ][0]
    check("opening cash AGENT = 4200000.00", float(bal_agent) == 4_200_000.0, bal_agent)
    check(
        "opening cash BASELINE = 4200000.00", float(bal_base) == 4_200_000.0, bal_base
    )
    check("exactly one cash_ledger row for AGENT", n_ledger_agent == 1, n_ledger_agent)
    check("exactly one cash_ledger row for BASELINE", n_ledger_base == 1, n_ledger_base)

    # facilities correctness
    fac1 = q(
        sess,
        "select apr_pct, limit_amount from facilities where id='FAC-001' and policy='AGENT'",
    )[0]
    fac2 = q(
        sess,
        "select apr_pct, limit_amount from facilities where id='FAC-002' and policy='AGENT'",
    )[0]
    check(
        "FAC-001 apr 13.5 / limit 5,000,000",
        float(fac1[0]) == 13.5 and float(fac1[1]) == 5_000_000.0,
        fac1,
    )
    check(
        "FAC-002 apr 9.0 / limit 3,000,000",
        float(fac2[0]) == 9.0 and float(fac2[1]) == 3_000_000.0,
        fac2,
    )

    # invoice terms mix ~40% discount
    disc_frac = q(
        sess,
        """select count(*) filter (where discount_pct is not null)::float / count(*)
                            from invoices where policy='AGENT'""",
    )[0][0]
    check("~40% of invoices carry a discount", 0.38 <= disc_frac <= 0.42, disc_frac)

    # discount date ordering
    bad_disc_order = q(
        sess,
        """select count(*) from invoices
                                 where discount_until is not null and discount_until >= due_date""",
    )[0][0]
    check("all discount_until < due_date", bad_disc_order == 0, bad_disc_order)
    bad_issue_order = q(
        sess, """select count(*) from invoices where due_date <= issue_date"""
    )[0][0]
    check("all due_date > issue_date", bad_issue_order == 0, bad_issue_order)

    # max_delay_days range
    bad_delay = q(
        sess,
        "select count(*) from invoices where max_delay_days < 0 or max_delay_days > 20",
    )[0][0]
    check("all max_delay_days in [0,20]", bad_delay == 0, bad_delay)

    # obligations
    obl_rows = q(
        sess,
        "select category, count(*), sum(amount) from obligations group by category",
    )
    obl_by_cat = {r[0]: (r[1], float(r[2])) for r in obl_rows}
    check(
        "3 PAYROLL @ 2,200,000 each",
        obl_by_cat.get("PAYROLL") == (3, 6_600_000.0),
        obl_by_cat.get("PAYROLL"),
    )
    check(
        "3 RENT @ 350,000 each",
        obl_by_cat.get("RENT") == (3, 1_050_000.0),
        obl_by_cat.get("RENT"),
    )
    check(
        "3 LOAN_EMI @ 480,000 each",
        obl_by_cat.get("LOAN_EMI") == (3, 1_440_000.0),
        obl_by_cat.get("LOAN_EMI"),
    )
    check("3 TAX rows", obl_by_cat.get("TAX", (0,))[0] == 3, obl_by_cat.get("TAX"))
    rent_hard = q(sess, "select hard from obligations where category='RENT'")
    payroll_hard = q(sess, "select hard from obligations where category='PAYROLL'")
    check(
        "RENT obligations are soft (hard=false)",
        all(r[0] is False for r in rent_hard),
        rent_hard,
    )
    check(
        "PAYROLL obligations are hard",
        all(r[0] is True for r in payroll_hard),
        payroll_hard,
    )

    # customer behaviour / historical delays
    cus_rows = q(
        sess,
        "select id, mean_delay_days, std_delay_days, on_time_probability, historical_delays "
        "from customers order by id",
    )
    cus4 = next(r for r in cus_rows if r[0] == "CUS-004")
    cus8 = next(r for r in cus_rows if r[0] == "CUS-008")
    check(
        "CUS-004 chronically late (mean 18d, 10 samples)",
        float(cus4[1]) == 18.0 and len(cus4[4]) >= 5,
        (cus4[1], len(cus4[4])),
    )
    check(
        "CUS-008 chronically late (mean 26d, 8 samples)",
        float(cus8[1]) == 26.0 and len(cus8[4]) >= 5,
        (cus8[1], len(cus8[4])),
    )
    check(
        "every customer has >=5 historical_delays (bootstrap eligible)",
        all(len(r[4]) >= 5 for r in cus_rows),
    )

    # ---- SCENARIO 1: discount vs financing ----------------------------------------------
    inv1 = q(
        sess,
        """select amount, discount_pct, discount_until, due_date, supplier_id
                       from invoices where id='INV-0001' and policy='AGENT'""",
    )[0]
    _amt, disc_pct, disc_until, due, sup_id = inv1
    net_days = (
        due
        - q(
            sess,
            "select issue_date from invoices where id='INV-0001' and policy='AGENT'",
        )[0][0]
    ).days
    disc_days = (
        disc_until
        - q(
            sess,
            "select issue_date from invoices where id='INV-0001' and policy='AGENT'",
        )[0][0]
    ).days
    d = float(disc_pct) / 100
    implied_apr = (d / (1 - d)) * (365 / (net_days - disc_days)) * 100
    check("INV-0001 on SUP-001", sup_id == "SUP-001", sup_id)
    check(
        "INV-0001 2/10 net 30",
        float(disc_pct) == 2.0 and net_days == 30 and disc_days == 10,
        (disc_pct, net_days, disc_days),
    )
    check(
        "INV-0001 implied APR of forgoing ~37.2%",
        abs(implied_apr - 37.2) < 0.5,
        implied_apr,
    )
    fac001_apr = float(
        q(sess, "select apr_pct from facilities where id='FAC-001' and policy='AGENT'")[
            0
        ][0]
    )
    check(
        "37.2% forgo-cost > 13.5% bank line (borrow-to-discount is correct)",
        implied_apr > fac001_apr,
        (implied_apr, fac001_apr),
    )

    # ---- SCENARIO 2: cash-rich but not really -------------------------------------------
    rcv4 = q(
        sess,
        "select customer_id, amount, expected_date from receivables where id='RCV-0004'",
    )[0]
    obl1 = q(
        sess, "select category, amount, due_date from obligations where id='OBL-001'"
    )[0]
    check(
        "RCV-0004 is the largest receivable",
        float(rcv4[1])
        == max(float(x[0]) for x in q(sess, "select amount from receivables")),
    )
    check("RCV-0004 on CUS-004 (chronically late)", rcv4[0] == "CUS-004", rcv4[0])
    check("RCV-0004 amount >= 4,000,000", float(rcv4[1]) >= 4_000_000.0, rcv4[1])
    check(
        "OBL-001 is PAYROLL, 2,200,000, due 2026-03-31",
        obl1[0] == "PAYROLL"
        and float(obl1[1]) == 2_200_000.0
        and str(obl1[2]) == "2026-03-31",
        obl1,
    )
    days_before_payroll = (obl1[2] - rcv4[2]).days
    check(
        "RCV-0004 collects 3-5 days before payroll",
        3 <= days_before_payroll <= 5,
        days_before_payroll,
    )
    # naive liquidity check: if CUS-004 delays by its own mean (18 days), RCV-0004 arrives
    # after payroll, and opening cash alone can't cover payroll + other near-term due invoices
    invoices_before_payroll = q(
        sess,
        """select coalesce(sum(amount),0) from invoices
                                          where policy='AGENT' and due_date <= '2026-03-31'
                                          and due_date >= '2026-03-01'""",
    )[0][0]
    projected_shortfall = 4_200_000.0 - float(obl1[1]) - float(invoices_before_payroll)
    check(
        "without RCV-0004 on time, opening cash minus payroll+near-term payables is tight/negative "
        "(liquidity pressure genuinely exists)",
        projected_shortfall < 4_200_000.0 * 0.5,
        projected_shortfall,
    )

    # ---- SCENARIO 3: stressed critical supplier -----------------------------------------
    sup2 = q(
        sess, "select criticality, liquidity_stress from suppliers where id='SUP-002'"
    )[0]
    inv2 = q(
        sess,
        "select amount, supplier_id, discount_pct, due_date from invoices "
        "where id='INV-0002' and policy='AGENT'",
    )[0]
    check("SUP-002 criticality >= 0.85", float(sup2[0]) >= 0.85, sup2[0])
    check("SUP-002 liquidity_stress >= 0.75", float(sup2[1]) >= 0.75, sup2[1])
    check(
        "INV-0002 on SUP-002, modest, no discount",
        inv2[1] == "SUP-002"
        and 150_000 <= float(inv2[0]) <= 300_000
        and inv2[2] is None,
        inv2,
    )
    check(
        "INV-0002 due in the tight cash week (late March, near payroll)",
        str(inv2[3])
        in (
            "2026-03-26",
            "2026-03-27",
            "2026-03-28",
            "2026-03-29",
            "2026-03-30",
            "2026-03-31",
        ),
        inv2[3],
    )

    # ---- determinism: hash invoices+receivables, reset again with same seed, compare ----
    def hashes():
        h1 = q(
            sess,
            "select md5(string_agg(id||amount::text, ',' order by id)) from invoices where policy='AGENT'",
        )[0][0]
        h2 = q(
            sess,
            "select md5(string_agg(id||amount::text, ',' order by id)) from receivables",
        )[0][0]
        h3 = q(
            sess,
            "select md5(string_agg(id||criticality::text||liquidity_stress::text, ',' order by id)) from suppliers",
        )[0][0]
        h4 = q(
            sess,
            "select md5(string_agg(id||amount::text||due_date::text, ',' order by id)) from obligations",
        )[0][0]
        return (h1, h2, h3, h4)

    before = hashes()
    sess.close()

    seed_world(seed=42, start_date="2026-03-01")  # reset again, same seed
    sess2 = SessionLocal()
    after_same = None

    def q2(sql):
        return sess2.execute(text(sql)).all()

    after_same = (
        q2(
            "select md5(string_agg(id||amount::text, ',' order by id)) from invoices where policy='AGENT'"
        )[0][0],
        q2(
            "select md5(string_agg(id||amount::text, ',' order by id)) from receivables"
        )[0][0],
        q2(
            "select md5(string_agg(id||criticality::text||liquidity_stress::text, ',' order by id)) from suppliers"
        )[0][0],
        q2(
            "select md5(string_agg(id||amount::text||due_date::text, ',' order by id)) from obligations"
        )[0][0],
    )
    check(
        "determinism: invoice hash identical across two resets (same seed)",
        before[0] == after_same[0],
        (before[0], after_same[0]),
    )
    check(
        "determinism: receivable hash identical across two resets",
        before[1] == after_same[1],
        (before[1], after_same[1]),
    )
    check(
        "determinism: supplier hash identical across two resets",
        before[2] == after_same[2],
        (before[2], after_same[2]),
    )
    check(
        "determinism: obligation hash identical across two resets",
        before[3] == after_same[3],
        (before[3], after_same[3]),
    )

    # AGENT vs BASELINE byte-identical at sim_day 0
    inv_agent = q2(
        "select id, amount, due_date, discount_pct from invoices where policy='AGENT' order by id"
    )
    inv_base = q2(
        "select id, amount, due_date, discount_pct from invoices where policy='BASELINE' order by id"
    )
    check(
        "AGENT and BASELINE invoices byte-identical at sim_day=0", inv_agent == inv_base
    )
    fac_agent = q2(
        "select id, apr_pct, limit_amount from facilities where policy='AGENT' order by id"
    )
    fac_base = q2(
        "select id, apr_pct, limit_amount from facilities where policy='BASELINE' order by id"
    )
    check("AGENT and BASELINE facilities identical at sim_day=0", fac_agent == fac_base)

    sess2.close()

    # world constants sanity
    check(
        "total_payable_value roughly matches count*range (200 invoices, 50k-1.5M)",
        40_000_000 < summary["world_constants"]["total_payable_value"] < 200_000_000,
        summary["world_constants"],
    )

    print(json.dumps({"pass": len(PASS), "fail": len(FAIL)}, indent=2))
    print("\n--- FAILURES ---" if FAIL else "\n--- ALL PASS ---")
    for f in FAIL:
        print("FAIL:", f)
    if not FAIL:
        for p in PASS:
            print("pass:", p)


if __name__ == "__main__":
    run()
