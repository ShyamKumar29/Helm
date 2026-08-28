# Phase B2 — Seed Data

**Window:** H+3 → H+5. Budget two hours, not one.
**Blocks:** the entire demo story.

> Read `13-SEED-DATA-SPEC.md` in full before starting. This file is the process; that file is
> the numbers.

---

## 1. Goal

Generate a plausible mid-size Indian manufacturing company, seeded identically into the AGENT
and BASELINE worlds, reproducible from a fixed RNG seed, containing three deliberately planted
situations that make the agent visibly smarter than the baseline.

**This is the phase where the demo is won or lost, and it is the one people rush.** A perfect
optimiser over boring data produces a boring scoreboard. Mediocre logic over well-planted data
produces a demo a judge remembers.

## 2. Files

```
api/seed/__init__.py
api/seed/generate.py        # the generator — deterministic, seeded
api/seed/planted.py         # the three planted situations, written by hand
api/seed/seed_data.json     # optional frozen snapshot, see step 6
```

## 3. Build steps

### Step 1 — one seeded generator, no global random

```python
# api/seed/generate.py
import numpy as np

def build_world(seed: int, start_date: date) -> WorldSpec:
    rng = np.random.default_rng(seed)
    ...
```

**Never call `random.random()` or `np.random.rand()` at module level.** Everything draws from
`rng`. If two runs of `/sim/reset` with the same seed produce different worlds, the demo
flickers and a judge notices — and you will not find the cause quickly at hour 20.

### Step 2 — generate in dependency order

Suppliers, then customers, then facilities, then obligations, then invoices, then receivables.
Invoices reference suppliers; receivables reference customers. Generating out of order means
foreign key failures you will fix by disabling constraints, which is the wrong fix.

Quantities and distributions are in `13-SEED-DATA-SPEC.md`. Summary:

| Entity | Count | Notes |
|---|---|---|
| suppliers | 40 | criticality 0.1–1.0, liquidity_stress 0.1–0.9, ~1/3 supplier-finance eligible |
| customers | 8 | five distinct payment personalities — see spec |
| invoices | 200 | log-normal ₹50,000–₹15,00,000, ~40% carry a discount |
| receivables | 60 | one ₹40,00,000+ on a chronically-late customer |
| obligations | ~12 | payroll month-end ₹22,00,000, GST 20th, rent 5th, EMI 10th |
| facilities | 2 | FAC-001 bank line ₹50,00,000 @ 13.5%; FAC-002 supplier finance ₹30,00,000 @ 9.0% |
| opening cash | — | ₹42,00,000 |

### Step 3 — plant the three situations by hand

Do not hope the random draw produces them. Write them explicitly in `planted.py` and
overwrite whatever the generator produced for those specific IDs.

**Situation 1 — borrow to take the discount.**
An invoice with `2/10 net 30` terms (implied cost of forgoing: 37.2% APR) against a bank line
at 13.5%, sized so that paying from cash would breach the liquidity floor. The agent borrows
and captures the discount; the baseline, which only pays early when `cash_available >
invoice.amount`, does not. Use `INV-0001` on `SUP-001` (Meenakshi Steels) so it matches the
fixture and the demo script.

**Situation 2 — cash-rich but not really.**
A week where cash looks healthy while payroll (₹22,00,000, month end) plus the large delayed
receivable means P5 cash goes negative. The agent holds; the baseline spends and misses
payroll. This is the situation the chaos preset #1 amplifies.

**Situation 3 — the stressed critical supplier.**
A small invoice from a supplier with `criticality >= 0.85` and `liquidity_stress >= 0.75`. A
pure-cost optimiser delays it; the supplier-stress term in the objective pays it anyway. This
is the proof that no single objective dominates, and it is what the weight sliders demonstrate
at 4:00 in the demo script.

Each planted situation gets a comment in `planted.py` naming the demo moment it serves. When
someone retunes the numbers at hour 17, the comment is what stops them destroying the story.

### Step 4 — the demo-critical IDs are fixed, not generated

These IDs are hardcoded in the frontend chaos panel presets. They must exist after every
reset, with these properties:

| ID | Must be | Why |
|---|---|---|
| `RCV-0004` | the largest receivable, on a chronically-late customer, collecting near month end | chaos preset #1, demo script 2:00 |
| `FAC-001` | the bank line, APR 13.5% | chaos preset #2 |
| `SUP-001` | Meenakshi Steels, criticality ~0.9 | chaos preset #4 |
| `INV-0001` | on SUP-001, 2/10 net 30 | the discount-economics talking point |
| `OBL-001` | payroll, ₹22,00,000, first month end in the horizon | the binding constraint |

**Tell Person C these five IDs out loud as soon as they are fixed.** Their preset buttons hard
code them; if a regenerate shuffles them, the judge clicks a button and gets a 404.

### Step 5 — seed both policies identically

```python
for policy in ("AGENT", "BASELINE"):
    insert_invoices(world.invoices,   policy=policy)
    insert_facilities(world.facilities, policy=policy)
    insert_cash_ledger_opening(world.opening_cash, policy=policy)
```

Suppliers, customers, receivables and obligations are **shared, single-copy** — they are the
outside world and both policies see the same one. Only invoices, facilities and cash are
policy-scoped, because those are what a decision changes.

The opening cash goes in as the first `cash_ledger` row per policy:
`delta = opening_cash`, `balance = opening_cash`, `reason = "OPENING_BALANCE"`.

### Step 6 — freeze a snapshot once the story lands

Once the planted situations produce a demo you like, dump the generated world to
`api/seed/seed_data.json` and have `/sim/reset` load the snapshot rather than re-running the
generator. Two reasons: it removes any residual RNG nondeterminism, and it makes reset
noticeably faster, which matters when you run it before every rehearsal.

Keep the generator working — you will want it during the H+16 tuning pass with Shyam.

## 4. Definition of done

- [ ] `POST /api/sim/reset` populates all tables, both policies, in under 3 seconds
- [ ] Two consecutive resets with the same seed produce identical row counts and identical
      checksums on `invoices` and `receivables`
- [ ] The five demo-critical IDs exist with the required properties
- [ ] All three planted situations are present and hand-verified with a query
- [ ] AGENT and BASELINE invoice sets are byte-identical at `sim_day = 0`
- [ ] Opening cash appears exactly once per policy in `cash_ledger`
- [ ] Person C has been told the five hardcoded IDs out loud

## 5. Verify

```bash
curl -s -X POST localhost:8000/api/sim/reset \
  -H 'content-type: application/json' -d '{"seed":42,"start_date":"2026-03-01"}'

psql() { docker compose exec -T db psql -U helm -d helm -c "$1"; }

psql "select policy, count(*) from invoices group by policy;"
# expect two rows, identical counts

psql "select count(*) from suppliers;"    # 40
psql "select count(*) from customers;"    # 8
psql "select count(*) from receivables;"  # 60

psql "select id, amount, expected_date from receivables order by amount desc limit 3;"
# RCV-0004 must be at the top, > 4000000

psql "select id, amount, discount_pct, discount_until, due_date from invoices
      where id='INV-0001' and policy='AGENT';"
# 2.0 discount, discount_until ~10 days after issue, due ~30 days after issue

psql "select id, label, amount, due_date from obligations where category='PAYROLL' order by due_date;"
# 2200000 on each month end

# determinism check — run reset twice, compare
psql "select md5(string_agg(id||amount::text, ',' order by id)) from invoices where policy='AGENT';"
```

Run that last hash before and after a second reset. Same value or the seed is leaking.
