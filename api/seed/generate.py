# api/seed/generate.py — B2. The seeded generator. No global randomness anywhere:
# every draw comes from `np.random.default_rng(seed)`, per docs/backend/05-PHASE-B2-seed-data.md
# step 1 and 13-SEED-DATA-SPEC.md section 10.1.
#
# Produces a plain-dict WorldSpec — not ORM objects. Keeps seed generation isolated from the
# DB layer (api/seed/seed.py inserts it) and from every later phase (forecast, engine gateway,
# optimisation, baseline, materiality, replay, comparison metrics — none of that lives here).
#
# Generation order matches the doc: suppliers, customers, facilities, obligations, invoices,
# receivables. Invoices reference suppliers; receivables reference customers.
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from api.services import ids

OPENING_CASH = 4_200_000.0

N_SUPPLIERS = 40
N_CUSTOMERS = 8
N_INVOICES = 200
N_RECEIVABLES = 60

DEFAULT_WEIGHTS = {
    "discount": 1.0,
    "financing_cost": 1.0,
    "penalty": 1.0,
    "liquidity_risk": 1.5,
    "supplier_stress": 0.8,
}

# 40 plausible Indian manufacturing supplier names. Static, not drawn from rng, so the name
# list itself never changes between runs regardless of seed — only which supplier gets which
# criticality/stress/eligibility draw depends on the seed.
_SUPPLIER_NAMES = [
    "Meenakshi Steels",
    "Karthik Polymers",
    "Ganesh Castings",
    "Anand Fasteners",
    "Rajan Metal Works",
    "Bharat Forgings",
    "Shakti Alloys",
    "Vishwakarma Tooling",
    "Om Sri Precision",
    "Lakshmi Wire Industries",
    "Sundaram Bearings",
    "Krishna Extrusions",
    "Deccan Sheet Metal",
    "Nataraj Machine Works",
    "Sri Balaji Fabrications",
    "Vijay Rubber Components",
    "Amman Industrial Coatings",
    "Prakash Springs & Dies",
    "Chola Hydraulics",
    "Murugan Precision Cast",
    "Saraswati Electricals",
    "Ashok Tube Mills",
    "Ramesh Forge Works",
    "Ganapathy Gears",
    "Trichy Turnings",
    "Coimbatore Castings",
    "Hindustan Fixtures",
    "Nandi Tool Room",
    "Kaveri Stampings",
    "Everest Fasteners",
    "Shree Ram Foundry",
    "Aravind Sheet Works",
    "Balaji Precision Parts",
    "Sri Venkateswara Auto Components",
    "Madurai Metal Craft",
    "Sona Wire Products",
    "Tirupati Forge & Cast",
    "Kalyan Engineering Works",
    "Vasavi Industrial Supplies",
    "Sanjeevi Machining",
]

_CUSTOMER_NAMES = [
    "Suraksha Traders",
    "Bharat Component Works",
    "Nandi Auto Parts",
    "Ashwin Motors",
    "Deccan Engineering",
    "Konkan Fabricators",
    "Malabar Industries",
    "Vindhya Metalcraft",
]

# Fixed customer personalities. Exact numbers from 13-SEED-DATA-SPEC.md section 3 — not
# drawn from rng, because the delay model's bootstrap needs these exact `historical_delays`
# arrays and the demo needs CUS-004/CUS-008 exactly this late.
_CUSTOMER_SPECS = [
    dict(
        mean_delay_days=-2.0,
        std_delay_days=1.5,
        on_time_probability=0.85,
        historical_delays=[0, 0, -3, 0, -2, 0, -1, 0],
    ),
    dict(
        mean_delay_days=0.5,
        std_delay_days=1.0,
        on_time_probability=0.80,
        historical_delays=[0, 1, 0, 0, 2, 0, 0, 1],
    ),
    dict(
        mean_delay_days=1.0,
        std_delay_days=1.5,
        on_time_probability=0.75,
        historical_delays=[0, 2, 0, 1, 0, 3, 0, 0],
    ),
    dict(
        mean_delay_days=18.0,
        std_delay_days=9.0,
        on_time_probability=0.15,
        historical_delays=[3, 12, 0, 21, 7, 9, 14, 2, 25, 19],
    ),
    dict(
        mean_delay_days=8.0,
        std_delay_days=5.0,
        on_time_probability=0.40,
        historical_delays=[5, 9, 2, 14, 7, 0, 11, 6],
    ),
    dict(
        mean_delay_days=10.0,
        std_delay_days=6.0,
        on_time_probability=0.35,
        historical_delays=[8, 15, 3, 12, 0, 9, 18, 5],
    ),
    dict(
        mean_delay_days=7.0,
        std_delay_days=4.0,
        on_time_probability=0.45,
        historical_delays=[6, 3, 11, 0, 8, 5, 9, 2],
    ),
    dict(
        mean_delay_days=26.0,
        std_delay_days=11.0,
        on_time_probability=0.10,
        historical_delays=[22, 31, 18, 35, 27, 20, 33, 24],
    ),
]

# receivable customer weights — the two chronically-late customers (index 3 = CUS-004,
# index 7 = CUS-008) carry a disproportionate share of receivable value/count.
_RECEIVABLE_CUSTOMER_WEIGHTS = np.array([1, 1, 1, 3, 1, 1, 1, 3], dtype=float)

# invoice terms mix — 13-SEED-DATA-SPEC.md section 4.
#   name, share, discount_pct, discount_days, net_days
_TERMS = [
    ("2/10 net 30", 0.20, 2.0, 10, 30),
    ("1/15 net 45", 0.10, 1.0, 15, 45),
    ("3/7 net 30", 0.10, 3.0, 7, 30),
    ("net 30", 0.20, None, None, 30),
    ("net 45", 0.20, None, None, 45),
    ("net 60", 0.20, None, None, 60),
]


def _lognormal_clip(
    rng: np.random.Generator, n: int, lo: float, hi: float, median: float, sigma: float
) -> np.ndarray:
    """Log-normal draw clipped to [lo, hi], median-parameterised so the shape stays legible."""
    draws = rng.lognormal(mean=np.log(median), sigma=sigma, size=n)
    return np.clip(draws, lo, hi)


def build_world(seed: int, start_date: date) -> dict:
    rng = np.random.default_rng(seed)

    # ---- suppliers -------------------------------------------------------------------
    supplier_ids = [ids.sup_id(i + 1) for i in range(N_SUPPLIERS)]
    criticality = np.round(rng.uniform(0.1, 1.0, N_SUPPLIERS), 2)
    liquidity_stress = np.round(rng.uniform(0.1, 0.9, N_SUPPLIERS), 2)

    # ~1/3 of 40 suppliers are supplier-finance eligible = 13. SUP-001 is always one of them
    # (13-SEED-DATA-SPEC.md section 2); draw the remaining 12 from the other 39.
    eligible = np.zeros(N_SUPPLIERS, dtype=bool)
    eligible[0] = True
    other_idx = rng.choice(np.arange(1, N_SUPPLIERS), size=12, replace=False)
    eligible[other_idx] = True

    suppliers = [
        dict(
            id=supplier_ids[i],
            name=_SUPPLIER_NAMES[i],
            criticality=float(criticality[i]),
            liquidity_stress=float(liquidity_stress[i]),
            supplier_finance_eligible=bool(eligible[i]),
        )
        for i in range(N_SUPPLIERS)
    ]

    # ---- customers ---------------------------------------------------------------------
    customer_ids = [ids.cus_id(i + 1) for i in range(N_CUSTOMERS)]
    customers = [
        dict(
            id=customer_ids[i],
            name=_CUSTOMER_NAMES[i],
            **_CUSTOMER_SPECS[i],
        )
        for i in range(N_CUSTOMERS)
    ]

    # ---- facilities ----------------------------------------------------------------------
    eligible_ids = [supplier_ids[i] for i in range(N_SUPPLIERS) if eligible[i]]
    facilities = [
        dict(
            id="FAC-001",
            type="BANK_LINE",
            limit_amount=5_000_000.0,
            drawn=0.0,
            apr_pct=13.5,
            min_draw=50_000.0,
            repayment_days=60,
            eligible_supplier_ids=None,
        ),
        dict(
            id="FAC-002",
            type="SUPPLIER_FINANCE",
            limit_amount=3_000_000.0,
            drawn=0.0,
            apr_pct=9.0,
            min_draw=25_000.0,
            repayment_days=45,
            eligible_supplier_ids=eligible_ids,
        ),
    ]

    # ---- obligations -----------------------------------------------------------------
    # 3 months in a 90-day horizon from start_date. Category order (payroll, tax, rent, emi)
    # fixes OBL-001 = the first payroll without any special-case ID juggling later.
    n_months = 3
    month_ends = []
    d = start_date.replace(day=1)
    for _ in range(n_months):
        if d.month == 12:
            nxt = d.replace(year=d.year + 1, month=1, day=1)
        else:
            nxt = d.replace(month=d.month + 1, day=1)
        month_ends.append(nxt - timedelta(days=1))
        d = nxt

    gst_amounts = np.round(rng.uniform(600_000, 900_000, n_months), 2)

    obligations = []
    n = 1
    for me in month_ends:
        obligations.append(
            dict(
                id=ids.obl_id(n),
                label=f"Payroll {me.strftime('%B %Y')}",
                category="PAYROLL",
                amount=2_200_000.0,
                due_date=me,
                hard=True,
            )
        )
        n += 1
    for i, me in enumerate(month_ends):
        gst_date = me.replace(day=20)
        obligations.append(
            dict(
                id=ids.obl_id(n),
                label=f"GST {gst_date.strftime('%B %Y')}",
                category="TAX",
                amount=float(gst_amounts[i]),
                due_date=gst_date,
                hard=True,
            )
        )
        n += 1
    for me in month_ends:
        rent_date = me.replace(day=5)
        obligations.append(
            dict(
                id=ids.obl_id(n),
                label=f"Rent {rent_date.strftime('%B %Y')}",
                category="RENT",
                amount=350_000.0,
                due_date=rent_date,
                hard=False,
            )
        )
        n += 1
    for me in month_ends:
        emi_date = me.replace(day=10)
        obligations.append(
            dict(
                id=ids.obl_id(n),
                label=f"Loan EMI {emi_date.strftime('%B %Y')}",
                category="LOAN_EMI",
                amount=480_000.0,
                due_date=emi_date,
                hard=True,
            )
        )
        n += 1

    # ---- invoices ----------------------------------------------------------------------
    invoice_supplier_idx = rng.integers(0, N_SUPPLIERS, N_INVOICES)
    amounts = _lognormal_clip(
        rng, N_INVOICES, 50_000, 1_500_000, median=300_000, sigma=0.6
    )
    issue_offsets = rng.integers(-30, 61, N_INVOICES)  # sim_day -30 .. +60
    penalty_bps = np.round(rng.uniform(2.0, 8.0, N_INVOICES), 1)
    max_delay = rng.integers(0, 21, N_INVOICES)  # 0..20 inclusive

    # deterministic terms assignment matching the share column exactly (200 * share is exact
    # for every row in _TERMS, so no rounding drift): shuffle a fixed-count array once.
    terms_pool = []
    for name, share, disc_pct, disc_days, net_days in _TERMS:
        terms_pool += [(name, disc_pct, disc_days, net_days)] * round(
            N_INVOICES * share
        )
    terms_assignment = rng.permutation(np.array(terms_pool, dtype=object))

    invoices = []
    for i in range(N_INVOICES):
        issue_date = start_date + timedelta(days=int(issue_offsets[i]))
        _, disc_pct, disc_days, net_days = terms_assignment[i]
        due_date = issue_date + timedelta(days=int(net_days))
        discount_until = (
            issue_date + timedelta(days=int(disc_days))
            if disc_days is not None
            else None
        )
        invoices.append(
            dict(
                id=ids.invoice_id(i + 1),
                supplier_id=supplier_ids[invoice_supplier_idx[i]],
                amount=round(float(amounts[i]), 2),
                issue_date=issue_date,
                due_date=due_date,
                discount_pct=float(disc_pct) if disc_pct is not None else None,
                discount_until=discount_until,
                penalty_bps_per_day=float(penalty_bps[i]),
                max_delay_days=int(max_delay[i]),
                status="OPEN",
            )
        )

    # ---- receivables ---------------------------------------------------------------------
    rcv_customer_idx = rng.choice(
        N_CUSTOMERS,
        size=N_RECEIVABLES,
        p=_RECEIVABLE_CUSTOMER_WEIGHTS / _RECEIVABLE_CUSTOMER_WEIGHTS.sum(),
    )
    rcv_amounts = _lognormal_clip(
        rng, N_RECEIVABLES, 200_000, 2_500_000, median=700_000, sigma=0.5
    )
    rcv_offsets = rng.integers(0, 76, N_RECEIVABLES)  # sim_day 0..75

    receivables = []
    for i in range(N_RECEIVABLES):
        receivables.append(
            dict(
                id=ids.rcv_id(i + 1),
                customer_id=customer_ids[rcv_customer_idx[i]],
                amount=round(float(rcv_amounts[i]), 2),
                expected_date=start_date + timedelta(days=int(rcv_offsets[i])),
                status="OPEN",
            )
        )

    world = dict(
        seed=seed,
        start_date=start_date,
        opening_cash=OPENING_CASH,
        weights=DEFAULT_WEIGHTS,
        suppliers=suppliers,
        customers=customers,
        facilities=facilities,
        obligations=obligations,
        invoices=invoices,
        receivables=receivables,
    )
    return world
