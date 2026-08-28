# 13 — Seed Data Specification

Read fully before phase B2. This is the file that decides whether the demo has a story.

---

## 1. The company

A mid-size Indian manufacturing company. Every number below is plausible for that profile,
which matters: a judge who works in finance will notice if invoice sizes do not match payroll
size, and the illusion collapses.

| Fact | Value |
|---|---|
| Opening cash | ₹42,00,000 |
| Start date | 2026-03-01 (`sim_day = 0`) |
| Horizon | 90 days |
| RNG seed | 42 |

## 2. Suppliers — 40

| Field | Distribution |
|---|---|
| `id` | `SUP-001` … `SUP-040` |
| `name` | Indian manufacturing names — Meenakshi Steels, Karthik Polymers, Ganesh Castings, Anand Fasteners, Rajan Metal Works, … |
| `criticality` | uniform 0.1–1.0, rounded to 2 dp |
| `liquidity_stress` | uniform 0.1–0.9, rounded to 2 dp |
| `supplier_finance_eligible` | true for ~13 of 40 (one third) |

**Fixed:** `SUP-001` = Meenakshi Steels, `criticality = 0.90`, `liquidity_stress = 0.35`,
`supplier_finance_eligible = true`. Chaos preset #4 targets it by ID and the demo script names
it out loud.

## 3. Customers — 8, with personalities

The delay model (`FINAL.md` section 11.4) is only interesting if the customers differ. Five
distinct personalities across eight customers:

| # | Personality | `mean_delay_days` | `std_delay_days` | `on_time_probability` | `historical_delays` |
|---|---|---|---|---|---|
| CUS-001 | pays early | -2.0 | 1.5 | 0.85 | `[0,0,-3,0,-2,0,-1,0]` |
| CUS-002 | on time | 0.5 | 1.0 | 0.80 | `[0,1,0,0,2,0,0,1]` |
| CUS-003 | on time | 1.0 | 1.5 | 0.75 | `[0,2,0,1,0,3,0,0]` |
| CUS-004 | **chronically late** | 18.0 | 9.0 | 0.15 | `[3,12,0,21,7,9,14,2,25,19]` |
| CUS-005 | drifts | 8.0 | 5.0 | 0.40 | `[5,9,2,14,7,0,11,6]` |
| CUS-006 | drifts | 10.0 | 6.0 | 0.35 | `[8,15,3,12,0,9,18,5]` |
| CUS-007 | drifts | 7.0 | 4.0 | 0.45 | `[6,3,11,0,8,5,9,2]` |
| CUS-008 | **chronically late** | 26.0 | 11.0 | 0.10 | `[22,31,18,35,27,20,33,24]` |

`historical_delays` must have at least 5 entries so the engine bootstraps empirically rather
than falling back to the normal — bootstrapping is what makes the fan chart's asymmetric shape
defensible when a judge asks how uncertainty is modelled.

**CUS-004 is Ashwin Motors.** Named in the chaos preset and in the demo script.

## 4. Invoices — 200, policy-scoped (400 rows total)

| Field | Rule |
|---|---|
| `id` | `INV-0001` … `INV-0200` |
| `supplier_id` | drawn across all 40 suppliers |
| `amount` | log-normal, clipped to ₹50,000 – ₹15,00,000 |
| `issue_date` | spread over `sim_day` -30 … +60 |
| `due_date` | `issue_date` + net days |
| terms | see the mix below |
| `penalty_bps_per_day` | uniform 2.0 – 8.0 |
| `max_delay_days` | uniform integer 0 – 20 |
| `status` | `OPEN` |
| `policy` | one identical copy for `AGENT`, one for `BASELINE` |

### Terms mix — about 40% carry a discount

| Terms | Share | `discount_pct` | discount days | net days | implied APR of forgoing |
|---|---|---|---|---|---|
| 2/10 net 30 | 20% | 2.0 | 10 | 30 | 37.2% |
| 1/15 net 45 | 10% | 1.0 | 15 | 45 | 12.3% |
| 3/7 net 30 | 10% | 3.0 | 7 | 30 | 47.9% |
| net 30 / 45 / 60 | 60% | null | — | 30/45/60 | — |

That spread is deliberate. `2/10 net 30` at 37.2% and `3/7 net 30` at 47.9% are **above** the
13.5% bank line, so borrowing to capture them is correct. `1/15 net 45` at 12.3% is **below**
it, so borrowing to capture that one is wrong. The agent must get both right; a naive
"always take the discount" rule cannot.

`discount_until = issue_date + discount_days`. `null` for no-discount invoices, with
`discount_pct` also `null`.

## 5. Receivables — 60, shared

| Field | Rule |
|---|---|
| `id` | `RCV-0001` … `RCV-0060` |
| `customer_id` | weighted so the two chronically-late customers carry a disproportionate value share |
| `amount` | log-normal, ₹2,00,000 – ₹25,00,000, plus the one large exception |
| `expected_date` | spread over `sim_day` 0 … 75 |
| `status` | `OPEN` |

**Fixed — `RCV-0004`:**

| Field | Value |
|---|---|
| `customer_id` | `CUS-004` (Ashwin Motors, chronically late) |
| `amount` | ₹42,00,000 |
| `expected_date` | 3–5 days before the first month-end payroll (`2026-03-26`–`2026-03-28`) |

This single row is the demo. It is the largest receivable, it sits on the worst-paying
customer, and it lands just before payroll — so the P10 band dives through zero the moment a
judge delays it. Chaos preset #1 targets it by ID.

## 6. Obligations — shared, ~12 over 90 days

| Category | Amount | Schedule |
|---|---|---|
| `PAYROLL` | ₹22,00,000 | last day of each month |
| `TAX` (GST) | ₹6,00,000 – ₹9,00,000 | 20th of each month |
| `RENT` | ₹3,50,000 | 5th of each month |
| `LOAN_EMI` | ₹4,80,000 | 10th of each month |

All `hard = true` except `RENT`, which is `hard = false` — one soft obligation gives the
optimiser something legitimate to trade against and proves the hard/soft distinction is real
rather than decorative.

**Fixed:** `OBL-001` = payroll, ₹22,00,000, due `2026-03-31`. This is the binding constraint
named in the demo script at 0:30 and in the `Forecast.binding_reason` string.

## 7. Facilities — 2, policy-scoped (4 rows)

| Field | FAC-001 | FAC-002 |
|---|---|---|
| `type` | `BANK_LINE` | `SUPPLIER_FINANCE` |
| `limit` | ₹50,00,000 | ₹30,00,000 |
| `drawn` | 0 | 0 |
| `apr_pct` | 13.5 | 9.0 |
| `min_draw` | ₹50,000 | ₹25,000 |
| `repayment_days` | 60 | 45 |
| `eligible_supplier_ids` | `null` | the ~13 eligible suppliers, including `SUP-001` |

`FAC-001` at 13.5% is the number the whole discount-economics argument rests on. Chaos preset
#2 raises it to 18%, which flips the marginal borrow-to-discount decisions but not the
`3/7 net 30` ones — a nicely legible partial flip.

## 8. The three planted situations

Written by hand in `api/seed/planted.py`, overwriting whatever the generator produced. Each
gets a comment naming the demo moment it serves.

### Situation 1 — borrow to take the discount
- `INV-0001`, supplier `SUP-001`, amount ≈ ₹8,50,000, terms `2/10 net 30`
- `discount_until` falls in the first week of the sim
- opening cash minus the buffer requirement is **less than** the invoice amount, so paying
  from cash breaches the floor
- **Agent:** `FINANCE_BANK` at 13.5% to capture a 37.2% implied return → `CHEAPER_FINANCING`
- **Baseline:** `cash > invoice.amount` is false on that day → misses the discount entirely
- **Serves:** demo script 3:00, the why-not panel

### Situation 2 — cash-rich but not really
- Around `2026-03-24` to `2026-03-31`, cash looks healthy
- Payroll `OBL-001` ₹22,00,000 lands on the 31st; `RCV-0004` ₹42,00,000 is due the 26th on the
  worst-paying customer
- P5 of the minimum future balance goes negative → `deployable_cash` collapses
- **Agent:** holds cash, `BUFFER_BREACH` on the alternatives
- **Baseline:** ₹5,00,000 fixed reserve, no forecast → spends, then misses payroll
- **Serves:** demo script 0:30 and 1:00; the `shortfall_days` and `obligations_missed` columns

### Situation 3 — the stressed critical supplier
- Pick a supplier with `criticality >= 0.85` and `liquidity_stress >= 0.75`
- Give them a modest invoice (₹1,50,000 – ₹3,00,000) whose due date sits in a tight cash week
- A pure-cost optimiser delays it; the supplier-stress term pays it anyway
- **Serves:** demo script 4:00 — drag the supplier-stress slider and watch it flip

## 9. Demo-critical IDs — tell Person C out loud

Hardcoded in the frontend chaos panel. If a regenerate shuffles them, the judge clicks a
button and gets a 404.

```
RCV-0004   largest receivable, CUS-004 Ashwin Motors, ₹42,00,000, due just before payroll
FAC-001    bank line, ₹50,00,000 @ 13.5%
SUP-001    Meenakshi Steels, criticality 0.90
INV-0001   on SUP-001, 2/10 net 30, ≈ ₹8,50,000
OBL-001    payroll, ₹22,00,000, due 2026-03-31
CUS-004    Ashwin Motors
```

## 10. Seeding rules

1. **Every draw comes from `np.random.default_rng(seed)`.** No module-level randomness.
2. **Generate in dependency order:** suppliers, customers, facilities, obligations, invoices,
   receivables.
3. **Shared vs policy-scoped:**
   - shared, one copy: suppliers, customers, receivables, obligations
   - policy-scoped, two identical copies: invoices, facilities, cash ledger opening row
4. **Opening cash** is the first `cash_ledger` row per policy: `delta = 4200000`,
   `balance = 4200000`, `reason = "OPENING_BALANCE"`.
5. **World constants** computed once at seed time and cached on `sim_state`, because the
   health score needs them every tick:
   - `total_obligations` — count of obligation rows
   - `total_payable_value` — sum of all invoice amounts for one policy
   - `total_discount_available` — sum of `amount × discount_pct / 100` over discounted invoices
6. **Apply `planted.py` last**, after the generator, so it always wins.
7. **Freeze to `seed_data.json`** once the story lands (phase B2 step 6).

## 11. Sanity queries after seeding

```sql
select count(*) from suppliers;                                  -- 40
select count(*) from customers;                                  -- 8
select policy, count(*) from invoices group by policy;           -- two rows, both 200
select count(*) from receivables;                                -- 60
select policy, count(*) from facilities group by policy;         -- two rows, both 2

select id, amount, expected_date from receivables order by amount desc limit 3;
-- RCV-0004 on top, ~4200000, late March

select count(*) filter (where discount_pct is not null)::float / count(*) from invoices
where policy='AGENT';                                            -- ~0.40

select category, count(*), sum(amount) from obligations group by category;

select balance from cash_ledger where policy='AGENT' order by id desc limit 1;   -- 4200000
select balance from cash_ledger where policy='BASELINE' order by id desc limit 1; -- 4200000
```
