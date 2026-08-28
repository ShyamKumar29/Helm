# HELM.md — Frontend build spec for Claude Code

You are building the `web/` folder only. Read this file fully before writing any code.
This is a 24-hour hackathon project. Ship working, demo-ready UI over perfect architecture.

---

## 1. What this product is

HELM is an autonomous working-capital management agent. It is not a dashboard — it makes
payment and financing decisions for a company (which supplier invoices to pay now, delay,
finance, or discount-capture) and explains every decision in plain English.

The person using this screen is either the founder narrating a live demo, or a hackathon judge
sitting down to poke at it. Every screen must read correctly with zero explanation and survive
being clicked on by a stranger.

**The single most important number on screen is `deployable_cash`** — the amount of today's
cash that is safe to spend without risking a future shortfall. Give it the most visual weight
on the page.

---

## 2. Design direction

A reference image is attached showing a mobile fintech app (wallet/finance tracker). Adapt its
**materials and mood**, not its literal mobile layout — we are building a dense desktop
dashboard, not a phone screen.

**Take from the reference:**
- The dark teal-to-charcoal gradient panel treatment — use this for the hero forecast panel,
  not the whole page background
- The soft off-white/light-gray page background behind white content cards
- Rounded corners throughout (12–16px on cards, pill-shaped on buttons/badges/nav)
- The clean, restrained sans-serif type with generous letter-spacing on small caps labels
  (see "SPEND", "SAVE", "INVEST", "BORROW" in the reference — all-caps, 11px, letter-spaced,
  muted color)
- The 2×2 (here: wider) metric-tile grid pattern with a small icon top-right of each tile
- The big-number treatment for the hero figure (`$524,381.62` in the reference →
  `deployable_cash` in ours)
- Soft, low-contrast bar/sparkline charts as secondary visual texture inside tiles
- Pill-shaped segmented controls (DAY / WEEK / MONTH / YEAR in the reference → your own
  filters if needed)
- Avatar + dropdown pattern for context switching, notification bell — reuse this pattern for
  the sim-day/agent-status area in the header

**Do NOT take literally:**
- Do not build a phone-width single-column mobile layout. This is a desktop dashboard —
  wide, dense, multi-panel, viewed on a laptop during a live demo.
- Do not use a plain white page. Page background should be a very dark charcoal
  (`#0B0E11`–`#12161A` range) — this is a finance/treasury product, and a dark base with
  bright white content cards reads more premium and more "terminal" than a fully light UI.
  Think: the reference's *header gradient panel* extended as the page's base mood, with
  card surfaces sitting on top of it slightly lighter, not a light page with dark accents.
- Do not use rainbow category colors. One accent color only (teal/emerald reads well against
  the dark base and nods to the reference's gradient). Reserve red/amber strictly for danger/
  warning states (shortfall, breach, distress).

**Token starting point** (adjust if you find something better, but stay in this family):

```
--bg-page:        #0B0E11
--bg-panel:        #12161A   (dark cards: decision queue, timeline)
--bg-panel-light:  #F4F6F5   (light cards, if any — use sparingly, mainly for print/export)
--surface-hero:    linear-gradient(160deg, #0F2E2B 0%, #0B0E11 70%)   (fan chart panel bg)
--accent:          #2DD4A7   (teal/emerald — primary accent, buttons, P50 line, positive)
--accent-dim:      #1B3B35   (accent used as a subtle fill/border)
--danger:          #E5484D   (shortfall, breach, negative delta)
--warning:         #E8A33D   (materiality flip, penalty accepted)
--text-primary:    #F2F4F3
--text-secondary:  #9AA5A1
--text-muted:      #5E6A66
--border:          #1E2428
--radius-card:     16px
--radius-pill:     999px
--font-display:    'Inter', system-ui, sans-serif   (or similar geometric sans)
--font-mono:       'JetBrains Mono', 'IBM Plex Mono', monospace   (all rupee figures, IDs)
```

Every rupee amount, ID (`INV-0001`, `DEC-000007`), percentage, and basis-point figure renders
in the monospace font. Everything else (labels, prose, headings) in the display font.

---

## 3. Page layout — single page, no routing

```
┌──────────────────────────────────────────────────────────────────────┐
│ HEADER  HELM · ● RUNNING · Day 12 / Mar 13 2026 · [step][play][reset]│
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────┤
│ Health   │ Deploy-  │ Buffer   │ Cash     │ Shortfall│ Savings  │Cost│
│ 74/100   │ able     │ Required │ Avail.   │ 0 days   │ /day     │Δ   │
│          │ ₹18.5L   │ ₹23.5L   │ ₹42L     │          │ ₹5,300   │-2.4L│
├──────────┴──────────┴──────────┴──────────┴──────────┴──────────┴────┤
│  LEFT — 60%                          │  RIGHT — 40%                  │
│  ┌─────────────────────────────────┐ │  ┌──────────────────────────┐ │
│  │ CashFanChart (gradient hero      │ │  │ DecisionQueue             │ │
│  │  panel, per section 2 tokens)    │ │  │  ActionCard × N            │ │
│  │  P10/P50/P90 band, zero line,    │ │  │   → WhyNotPanel (expand)   │ │
│  │  binding_date marker             │ │  │   → "Why?" opens           │ │
│  └─────────────────────────────────┘ │  │      ExplanationPanel      │ │
│  ┌─────────────────────────────────┐ │  └──────────────────────────┘ │
│  │ Scoreboard — AGENT vs BASELINE   │ │  ┌──────────────────────────┐ │
│  │  side by side                    │ │  │ ActivityTimeline           │ │
│  └─────────────────────────────────┘ │  │  scrolling log feed         │ │
│                                       │  └──────────────────────────┘ │
├───────────────────────────────────────┴────────────────────────────────┤
│ BOTTOM  ChaosPanel (4 preset buttons + custom form) · WeightSliders    │
└──────────────────────────────────────────────────────────────────────┘
```

Build components in this priority order (stop and demo-check after each):

1. **Shared utilities first** — `src/utils/format.ts` and `src/utils/reason.ts` (see section 6).
   Every component depends on these.
2. **`CashFanChart`** — the hero. Gradient panel background, Recharts `AreaChart`, shaded
   P10–P90 band, solid P50 line in accent color, dashed red zero line, marker + label on
   `binding_date`. `deployable_cash` printed large above or inside the panel.
3. **KPI strip** — 7 metric tiles per the reference's tile pattern (icon top-right, label
   top-left in small caps, big number, small delta/sub-label below).
4. **`DecisionQueue`** + **`ActionCard`** — one card per invoice: supplier name, amount
   (monospace), due date, action as a colored pill (see `ACTION_COLOR` map), funding source,
   one-line reason. Click to expand `WhyNotPanel`.
5. **`WhyNotPanel`** — small table inside the expanded card: alternative action, net value,
   delta, reason code (mapped to human text). This is the PS-required trade-off disclosure —
   make it visually distinct, not an afterthought.
6. **`ExplanationPanel`** — slide-out or modal from a "Why?" button. Headline (bold), narrative
   (prose paragraph), key assumptions (small list), trade-offs (small list), and
   **"Would change if…"** in a visually distinct callout (accent-colored left border) — this
   is the section judges respond to most.
7. **`Scoreboard`** — agent vs baseline side-by-side metric comparison. Baseline's shortfall
   days rendered in danger red. Headline number: `delta.net_working_capital_cost`.
8. **`ActivityTimeline`** — scrolling log feed. Entries where the agent declined to
   re-optimize (materiality below threshold) render in a muted/lighter style than entries
   where it acted — this contrast is what shows engineering judgment.
9. **`ChaosPanel`** — 4 hardcoded preset buttons (see section 5) + optional custom form.
10. **`WeightSliders`** — 5 sliders for objective weights, debounced on release, not on drag.

Every component must render a sane fallback on missing/null data — build a single
`<EmptyState icon text />` component at step 1 and use it everywhere. The API may be broken
mid-demo; nothing should white-screen.

---

## 4. Data contracts (the shapes you're rendering)

Build entirely against **mock JSON fixtures** first — no backend dependency to start. Put
fixtures in `src/mocks/` matching these shapes exactly (field names are `snake_case`,
frozen — never camelCase them):

### State
```json
{
  "as_of": "2026-03-01", "sim_day": 0, "cash_available": 4200000.0,
  "suppliers": [{"id":"SUP-001","name":"Meenakshi Steels","criticality":0.9,"liquidity_stress":0.35,"supplier_finance_eligible":true}],
  "customers": [{"id":"CUS-004","name":"Ashwin Motors","mean_delay_days":8.0,"std_delay_days":6.0,"on_time_probability":0.35,"historical_delays":[3,12,0,21,7,9,14,2]}],
  "invoices": [{"id":"INV-0001","supplier_id":"SUP-001","amount":850000.0,"issue_date":"2026-02-20","due_date":"2026-03-22","discount_pct":2.0,"discount_until":"2026-03-02","penalty_bps_per_day":5.0,"max_delay_days":15,"status":"OPEN"}],
  "receivables": [{"id":"RCV-0001","customer_id":"CUS-004","amount":1250000.0,"expected_date":"2026-03-10","status":"OPEN"}],
  "obligations": [{"id":"OBL-001","label":"Payroll March","category":"PAYROLL","amount":2200000.0,"due_date":"2026-03-31","hard":true}],
  "facilities": [{"id":"FAC-001","type":"BANK_LINE","limit":5000000.0,"drawn":0.0,"apr_pct":13.5,"min_draw":50000.0,"repayment_days":60,"eligible_supplier_ids":null}]
}
```

### Forecast
```json
{
  "generated_at":"2026-03-01","sim_day":0,"horizon_days":90,"n_paths":2000,"risk_alpha":0.05,
  "buckets":[{"date":"2026-03-01","day_offset":0,"p10":3980000.0,"p50":4200000.0,"p90":4200000.0,"shortfall_prob":0.0,"committed_outflow":0.0,"expected_inflow":0.0}],
  "deployable_cash":1850000.0,"buffer_required":2350000.0,"binding_date":"2026-03-31",
  "binding_reason":"OBL-001 payroll, with RCV-0001 collecting late in the 5th percentile path",
  "worst_case_min_cash":-180000.0
}
```
`buckets` has `horizon_days + 1` entries. Plot `p10`/`p50`/`p90` directly as the fan chart.

### DecisionObject (the most important one)
```json
{
  "decision_id":"DEC-000007","run_at":"2026-03-13","sim_day":12,"policy":"AGENT",
  "trigger":{"type":"EVENT","event_id":"EVT-0031","materiality_score":0.42,"description":"RCV-0004 expected collection date pushed out by 21 days"},
  "cash_before":4200000.0,"buffer_required":2350000.0,"deployable_cash":1850000.0,
  "objective_weights":{"discount":1.0,"financing_cost":1.0,"penalty":1.0,"liquidity_risk":1.5,"supplier_stress":0.8},
  "objective_value":128400.0,
  "actions":[{
    "action_id":"ACT-0001","target_type":"INVOICE","target_id":"INV-0001","supplier_id":"SUP-001",
    "action":"PAY_EARLY_DISCOUNT","amount":833000.0,"execute_on":"2026-03-14",
    "funding_source":"BANK_LINE","facility_id":"FAC-001","confidence":0.86,
    "score_breakdown":{"discount_captured":17000.0,"penalty_incurred":0.0,"financing_cost":4100.0,"liquidity_risk_cost":1200.0,"supplier_stress_delta":-0.08,"net_value":11700.0},
    "binding_constraints":["BUFFER_FLOOR"],"primary_reason_code":"CHEAPER_FINANCING",
    "rejected_alternatives":[
      {"action":"PAY_AT_MATURITY","net_value":0.0,"delta":-11700.0,"reason_code":"DISCOUNT_FORGONE"},
      {"action":"PAY_NOW","net_value":-3400.0,"delta":-15100.0,"reason_code":"BUFFER_BREACH"}
    ],
    "status":"PROPOSED"
  }],
  "facility_actions":[{"facility_id":"FAC-001","action":"DRAW","amount":833000.0,"expected_repay_date":"2026-05-13","interest_cost":25600.0}],
  "solver":{"method":"MILP_SCENARIO","status":"OPTIMAL","solve_ms":740,"n_scenarios":5,"fallback_used":false},
  "diff_from_previous":{"previous_decision_id":"DEC-000006","flipped":[{"target_id":"INV-0007","from":"PAY_NOW","to":"DELAY","reason_code":"BUFFER_BREACH"}],"added":[],"removed":[]},
  "explanation":null
}
```
**Every open invoice has an entry in `actions[]`** — a HOLD is explicit, never inferred from
absence. `rejected_alternatives` always has ≥1 entry.

### Explanation
```json
{
  "decision_id":"DEC-000007",
  "headline":"Holding cash for payroll, financing the Meenakshi invoice instead",
  "narrative":"A large receivable from Ashwin Motors moved out by three weeks, which drops fifth-percentile cash below zero around the 31st when payroll of ₹22,00,000 lands. Paying INV-0001 from cash would breach that floor, so the agent drew ₹8,33,000 on the bank line at 13.5% to capture the 2% early-payment discount worth ₹17,000. Borrowing cost ₹4,100 over the discount window, so the trade nets ₹11,700.",
  "key_assumptions":["Ashwin Motors collects on the revised date with its historical 8-day mean delay","Bank line remains available at 13.5% through the repayment window","Payroll of ₹22,00,000 on 31 March is a hard constraint and cannot slip"],
  "tradeoffs":["Accepted ₹25,600 of interest exposure to preserve ₹8,33,000 of liquidity","Accepted a ₹4,200 late penalty on INV-0007 rather than breach the liquidity floor"],
  "would_change_if":["If RCV-0004 collects on its original date, INV-0007 returns to PAY_NOW","If the bank line APR rises above 37%, forgoing the discount becomes cheaper","If SUP-001 liquidity stress rises above 0.7, the agent pays from cash regardless"],
  "generated_by":"template",
  "grounded_fields":["cash_before","buffer_required","deployable_cash","actions[0].score_breakdown","facility_actions[0].interest_cost"]
}
```

### Event
```json
{
  "event_id":"EVT-0031","sim_day":12,"date":"2026-03-13","type":"RECEIVABLE_DELAYED","source":"JUDGE_INJECTED",
  "payload":{"receivable_id":"RCV-0004","new_expected_date":"2026-04-03","delay_days":21},
  "materiality_score":0.42,"triggered_reoptimization":true,"triggered_decision_id":"DEC-000007"
}
```

### ComparisonMetrics (scoreboard)
```json
{
  "sim_day":45,"as_of":"2026-04-15",
  "agent":{"discounts_captured":184000.0,"financing_cost":62400.0,"penalties_paid":8400.0,"net_working_capital_cost":-113200.0,"shortfall_days":0,"min_cash_seen":640000.0,"obligations_missed":0,"avg_supplier_stress":0.31,"decisions_made":19,"reoptimizations_triggered":7,"health_score":82,"savings_per_day":5316.0},
  "baseline":{"discounts_captured":41000.0,"financing_cost":118900.0,"penalties_paid":47600.0,"net_working_capital_cost":125500.0,"shortfall_days":3,"min_cash_seen":-420000.0,"obligations_missed":1,"avg_supplier_stress":0.58,"decisions_made":45,"reoptimizations_triggered":0,"health_score":41,"savings_per_day":-2789.0},
  "delta":{"net_working_capital_cost":-238700.0,"shortfall_days":-3,"obligations_missed":-1,"health_score":41}
}
```
`net_working_capital_cost = financing_cost + penalties_paid - discounts_captured`. Lower/
negative is better. `health_score` (0–100) drives the KPI tile color band: 80+ green,
50–79 amber, <50 red.

---

## 5. Chaos panel — hardcoded demo presets

Build these as one-click preset buttons (custom override form is optional/lower priority):

| Button label | Event type | Target | Payload |
|---|---|---|---|
| "Ashwin Motors pays 3 weeks late" | `RECEIVABLE_DELAYED` | `RCV-0004` | `{delay_days: 21}` |
| "Bank rate jumps to 18%" | `RATE_CHANGE` | `FAC-001` | `{new_apr_pct: 18.0}` |
| "Emergency GST notice ₹9L in 5 days" | `NEW_OBLIGATION` | — | `{amount: 900000, category: "TAX"}` |
| "Meenakshi Steels in distress" | `SUPPLIER_DISTRESS` | `SUP-001` | `{new_liquidity_stress: 0.85}` |

When a preset fires (call it against the mock/API, whichever is wired), run this visual
sequence — this is the entire demo moment, get it smooth:

1. Header status pill → `⟳ RE-OPTIMIZING` (warning color)
2. KPI tiles grey out briefly (~50ms)
3. Fan chart redraws with new bands
4. Any flipped decision cards get a pulsing accent/warning border for ~3s
5. New timeline entries scroll in, including the materiality-score log line
6. KPI tiles and health score update to post-shock values
7. Header status pill → `● RUNNING` (accent/success color)

All transitions under 300ms individually. No spinner-heavy loading — this should feel like
the agent thinking, not a page reload.

---

## 6. Shared utilities — build these first

`src/utils/format.ts`:
```typescript
export function inr(amount: number): string {
  const abs = Math.abs(amount);
  const sign = amount < 0 ? "-" : "";
  if (abs >= 10000000) return `${sign}₹${(abs / 10000000).toFixed(2)} Cr`;
  if (abs >= 100000)   return `${sign}₹${(abs / 100000).toFixed(2)} L`;
  return `${sign}₹${abs.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
export function inrExact(amount: number): string {
  return `₹${Math.abs(amount).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
export function bps(value: number): string { return `${value.toFixed(1)} bps/day`; }
export function pct(value: number): string { return `${value.toFixed(1)}%`; }
export function simDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}
```

`src/utils/reason.ts` — never show a raw enum in the UI, always pass through these:
```typescript
export const REASON_TEXT: Record<string, string> = {
  BUFFER_BREACH: "Paying would breach the liquidity floor",
  DISCOUNT_CAPTURED: "Early-payment discount captured",
  DISCOUNT_FORGONE: "Discount forgone — liquidity preserved instead",
  PENALTY_AVOIDED: "Penalty avoided by paying on time",
  PENALTY_ACCEPTED: "Penalty accepted — cheaper than the alternative",
  FACILITY_LIMIT: "Facility headroom exhausted",
  OBLIGATION_PRIORITY: "Cash reserved for an upcoming hard obligation",
  SUPPLIER_CRITICAL: "Strategic supplier — prioritised for relationship",
  SUPPLIER_DISTRESS: "Supplier under liquidity stress — early payment",
  CHEAPER_FINANCING: "Borrowing is cheaper than forgoing the discount",
  INSUFFICIENT_CASH: "Insufficient cash for this action",
  NO_BETTER_ALTERNATIVE: "No better alternative exists",
};
export const ACTION_TEXT: Record<string, string> = {
  PAY_NOW: "Pay now from cash", PAY_EARLY_DISCOUNT: "Pay early to capture discount",
  PAY_AT_MATURITY: "Pay at maturity", DELAY: "Delay payment",
  FINANCE_BANK: "Finance via bank line", FINANCE_SUPPLIER: "Finance via supplier program",
  HOLD: "Hold — revisit next cycle",
};
export const ACTION_COLOR: Record<string, string> = {
  PAY_NOW: "accent", PAY_EARLY_DISCOUNT: "accent", PAY_AT_MATURITY: "info",
  DELAY: "warning", FINANCE_BANK: "purple", FINANCE_SUPPLIER: "purple", HOLD: "muted",
};
export const EVENT_TEXT: Record<string, string> = {
  DAY_ADVANCED: "Day advanced", RECEIVABLE_DELAYED: "Receivable delayed",
  RECEIVABLE_COLLECTED: "Receivable collected", NEW_INVOICE: "New invoice received",
  INVOICE_PAID: "Invoice paid", RATE_CHANGE: "Financing rate changed",
  NEW_OBLIGATION: "New obligation added", SUPPLIER_DISTRESS: "Supplier under distress",
  CASH_INJECTION: "Cash injection received",
};
```

---

## 7. Tech stack

- Vite + React + TypeScript
- Recharts for the fan chart (only chart library — don't add a second one)
- Tailwind for styling, tokens from section 2 wired into `tailwind.config` theme extension
- No routing library needed — single page
- `USE_MOCK` env flag pattern in `src/api/client.ts`: read from `src/mocks/*.json` until a
  real backend exists, then flip one variable to hit `fetch(...)`. Build 100% of the UI
  against mocks first.

---

## 8. Rules

- `snake_case` in all data types/interfaces to match the backend contracts exactly. Do not
  camelCase any field coming from or going to the API.
- Money is always a `number` (float), formatted only at render time via `inr()`. Never
  compare money with `===` after arithmetic.
- Dates are ISO `"YYYY-MM-DD"` strings, no timezones. Time within the sim is `sim_day` (int).
- Every component handles `null`/missing data with `<EmptyState>` — never crash, never
  white-screen.
- No animation over 300ms anywhere.
- This is a demo product for a live 5-minute pitch — prioritize looking finished and reacting
  smoothly to the chaos panel over architectural purity.
