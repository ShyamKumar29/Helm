<div align="center">

# HELM

**An autonomous working-capital management agent.**

*"A company's treasurer decides every morning where limited cash goes. He does it with static rules, and those rules break the moment a customer pays late. We replaced him."*

Built for **CSI ORIGIN 2026** — Problem Statement 4 — by **Team XYRUS**, in a 24-hour build window.

</div>

---

## Table of contents

- [What HELM is](#what-helm-is)
- [Why it's not "a dashboard"](#why-its-not-a-dashboard)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Ownership map](#ownership-map)
- [Data contracts](#data-contracts)
- [Chaos panel — the demo moment](#chaos-panel--the-demo-moment)
- [Tech stack](#tech-stack)
- [Getting started](#getting-started)
- [Project status](#project-status)
- [Engineering rules](#engineering-rules)
- [Checkpoints](#checkpoints)
- [Scope cuts](#scope-cuts-in-priority-order)

---

## What HELM is

HELM is an autonomous agent that makes **payment and financing decisions** for a company — which
supplier invoices to pay now, delay, finance, or capture an early-payment discount on — and
**explains every decision in plain English**.

It is not a static rules engine, and it is not a BI dashboard bolted onto a spreadsheet. Every
morning (or every simulated day), it:

1. **Forecasts** cash flow 90 days out using Monte Carlo simulation over receivable delays,
   financing costs, and obligations — producing a P10/P50/P90 uncertainty band, not a single
   point estimate.
2. **Decides** what to do with every open invoice — pay now, pay early for a discount, delay,
   or finance via a bank line — by solving a constrained optimization (MILP over scenarios,
   with a guaranteed greedy fallback under a 2-second timeout).
3. **Explains** the decision it already made, in prose, grounded in the actual numbers the
   optimizer produced. The language model never computes a number — it only narrates a decision
   object that already exists.

The single most important number on screen is **`deployable_cash`** — the amount of today's
cash that is safe to spend without risking a future shortfall. It is what makes this project a
decision system, not a dashboard.

## Why it's not "a dashboard"

Most finance tooling shows you what happened. HELM commits to what to do next, and — critically —
**shows its work**:

- Every open invoice gets an explicit action. A `HOLD` is a decision, never an absence.
- Every action ships with `rejected_alternatives[]` — the roads not taken, and why, with a
  numeric delta.
- Every decision can be explained on demand, with an explicit **"would change if…"** section
  naming the exact conditions under which the agent would have decided differently.
- The agent is benchmarked continuously against a static-rules baseline, side by side, so the
  value of adaptive decision-making is never just asserted — it's measured.

## Architecture

```
                 ┌─────────────┐
                 │  contracts/ │   Pydantic models — frozen at H+1, single source of truth
                 └──────┬──────┘   for every shape crossing a boundary
                        │
         ┌──────────────┼───────────────┐
         │              │               │
   ┌─────▼─────┐  ┌─────▼─────┐  ┌──────▼──────┐
   │  engine/  │  │   api/    │  │ explainer/  │
   │           │  │           │  │             │
   │ Pure fn:  │  │ Serves    │  │ LLM narrates│
   │ State →   │  │ State,    │  │ a Decision- │
   │ Forecast  │  │ Forecast, │  │ Object that │
   │ → Decision│  │ Decision  │  │ already     │
   │           │  │ over HTTP │  │ exists      │
   │ No DB, no │  │           │  │             │
   │ network,  │  │ Computes  │  │ Never       │
   │ no stdout │  │ health_   │  │ computes a  │
   │           │  │ score     │  │ number      │
   └───────────┘  └─────┬─────┘  └─────────────┘
                        │
                  ┌─────▼─────┐
                  │   web/    │   Single-page dashboard, dark instrument-panel UI
                  │           │   USE_MOCK flag: built against fixtures, flips to
                  │           │   the live API with one variable
                  └───────────┘
```

**The engine is a pure function of `State`.** Dicts/Pydantic models in, dicts out — no database,
no environment variables, no network calls, no stdout. Given the same `(sim_day, decision_id)`
seed, it produces the same decision every time.

## Repository layout

```
Helm/
├── CLAUDE.md              # Non-negotiable project rules (this file never changes)
├── HELM.md                # Full frontend build spec: design tokens, layout, data contracts
├── design-reference.png   # Visual reference adapted for web/'s design direction
├── contracts/             # (pending) Pydantic models + frozen fixtures — shared by all folders
├── engine/                # (pending) Forecast + decision engine — owned by Shyam
├── api/                   # (pending) HTTP layer serving engine output
├── explainer/             # (pending) LLM narration layer — owned by Person C
└── web/                   # React dashboard — owned by Person C
    ├── src/
    │   ├── components/    # Header, KpiStrip, CashFanChart, EmptyState, icons/
    │   ├── utils/         # format.ts (inr, bps, pct, simDate), reason.ts (enum → text maps),
    │   │                  # motion.ts (shared framer-motion variants)
    │   ├── mocks/         # Fixtures matching the frozen data contracts exactly
    │   ├── api/client.ts  # USE_MOCK flag — swap fixtures for a live API in one line
    │   └── types.ts       # snake_case TypeScript interfaces mirroring the Python contracts
    └── ...
```

## Ownership map

| Folder | Owner | Rule |
|---|---|---|
| `engine/` | Shyam | Never edited outside by others |
| `api/` | Person B | Never edited outside by others |
| `explainer/`, `web/` | Person C | Never edited outside by others |
| `contracts/` | Shared | Frozen at H+1 — any change is announced and logged in `contracts/CHANGELOG.md` |

Branches: `feat/engine`, `feat/api`, `feat/web`. `main` is merged only at checkpoints.

## Data contracts

All contract field names are `snake_case` and frozen — never camelCased on the frontend, even
though the UI layer is TypeScript. The core shapes (see `HELM.md` §4 and `web/src/types.ts` for
full definitions):

| Contract | Purpose |
|---|---|
| `State` | Ground truth as of a given `sim_day`: cash, suppliers, customers, invoices, receivables, obligations, facilities |
| `Forecast` | 90-day Monte Carlo cash projection — `p10`/`p50`/`p90` buckets, `deployable_cash`, `buffer_required`, `binding_date` |
| `DecisionObject` | One decision run: an `actions[]` entry for **every** open invoice, each with `rejected_alternatives[]` and a `reason_code` enum |
| `Explanation` | LLM-generated narrative for a `DecisionObject` — headline, prose, assumptions, trade-offs, `would_change_if[]` |
| `Event` | A state-changing occurrence (late payment, rate change, new obligation, supplier distress) — may trigger re-optimization |
| `ComparisonMetrics` | Agent vs. static-baseline policy, side by side, including the `health_score` (0–100) that drives the KPI color band |

`net_working_capital_cost = financing_cost + penalties_paid - discounts_captured` — lower
(more negative) is better. The engine emits `reason_code` enums only, never prose; English is
generated exclusively in `explainer/`, and every enum the UI shows must pass through the
`REASON_TEXT` / `ACTION_TEXT` / `EVENT_TEXT` lookup maps in `web/src/utils/reason.ts`.

## Chaos panel — the demo moment

Four hardcoded, one-click presets simulate a live shock and trigger agent re-optimization —
no form-filling in front of a judge:

| Preset | Event type | Target | Payload |
|---|---|---|---|
| Ashwin Motors pays 3 weeks late | `RECEIVABLE_DELAYED` | `RCV-0004` | `delay_days: 21` |
| Bank rate jumps to 18% | `RATE_CHANGE` | `FAC-001` | `new_apr_pct: 18.0` |
| Emergency GST notice ₹9L in 5 days | `NEW_OBLIGATION` | — | `amount: 900000, category: TAX` |
| Meenakshi Steels in distress | `SUPPLIER_DISTRESS` | `SUP-001` | `new_liquidity_stress: 0.85` |

Firing a preset runs a scripted visual sequence — status pill flips to `⟳ RE-OPTIMIZING`, the KPI
strip greys out, the fan chart redraws with new bands, flipped decisions pulse an amber border,
new timeline entries scroll in, then the status pill returns to `● RUNNING` — with every
individual transition kept under 300ms so the demo never feels laggy.

## Tech stack

**`web/`** (the only folder with runnable code so far):

| Layer | Choice |
|---|---|
| Build tool | Vite |
| Framework | React 19 + TypeScript |
| Styling | Tailwind CSS |
| Charts | Recharts (fan chart with P10/P50/P90 bands) |
| Animation | Framer Motion |
| Icons | lucide-react + hand-drawn SVGs (`HelmWheel`, `CompassRose`) |
| Fonts | Geist Sans / Geist Mono (self-hosted via Fontsource) for all instrument/numeric content, Fraunces italic for narrative text |
| Data | `USE_MOCK` flag in `src/api/client.ts` — fixtures in `src/mocks/` until a live API exists |

**Planned** for `engine/` / `api/` / `explainer/`: Python, Pydantic for every boundary-crossing
model, `ruff format` for formatting, type hints on all public functions.

## Getting started

Currently only the frontend is buildable. From the repo root:

```bash
cd web
npm install
npm run dev
```

The dev server runs against the mock fixtures in `web/src/mocks/` — no backend required. Once
`api/` exists, flip `USE_MOCK` to `false` in `web/src/api/client.ts` and set `VITE_API_BASE` to
point at it.

Other useful commands (run from `web/`):

```bash
npm run build     # tsc -b && vite build — production build
npm run lint       # oxlint
npm run preview    # preview a production build locally
```

## Project status

**Built:**
- Project scaffolding (Vite + React + TS + Tailwind)
- Shared utilities: `format.ts`, `reason.ts`, `motion.ts`
- Mock fixtures for all six data contracts
- `Header` — status pill, sim-day/date, playback controls, avatar/notification pattern
- `KpiStrip` — 7-tile KPI row with a live-updating health gauge and sparkline texture
- `CashFanChart` — the hero: P10/P50/P90 band, zero line, binding-date marker, 30D/60D/90D
  range control, animated `deployable_cash` figure

**Pending** (per `HELM.md` §3's build order):
- `DecisionQueue` + `ActionCard`
- `WhyNotPanel` (the PS-required trade-off disclosure)
- `ExplanationPanel` (headline, narrative, assumptions, trade-offs, **"would change if…"**)
- `Scoreboard` — agent vs. baseline
- `ActivityTimeline`
- `ChaosPanel` + `WeightSliders`
- `contracts/`, `engine/`, `api/`, `explainer/` (owned by teammates)

## Engineering rules

The full list lives in `CLAUDE.md`; the ones that shape every contribution:

1. **Stay in your own folder.** Cross-folder edits happen by conversation, not by commit.
2. **Contracts are frozen at H+1.** Build against `contracts/fixtures/*.json`, never against
   another person's running code.
3. **The engine is a pure function of `State`.** No database, no env vars, no network, no stdout.
4. **The LLM never computes a number.** It only narrates a decision that already exists.
5. **The engine emits `reason_code` enums, never prose.**
6. **Deterministic output** — same `(sim_day, decision_id)` seed, same decision, every time.
7. **Never let a solve hang** — hard 2-second timeout, then a greedy fallback with
   `solver.fallback_used = true`.
8. **Never show a raw enum in the UI** — every enum passes through a `*_TEXT` lookup map, updated
   in the same commit that adds the enum value.
9. **Every component must survive null data** — the `<EmptyState>` pattern, everywhere.
10. **Indian rupee formatting everywhere** — `inr()` renders `₹42,00,000`, lakhs and crores, never
    `₹4,200,000`.

## Checkpoints

| Milestone | Deliverable |
|---|---|
| H+8 | `state → forecast → decide` end to end |
| **H+12** | **One invoice through the entire pipeline, including the LLM narrative** |
| H+16 | Full 90-day replay, agent vs. baseline |
| H+19 | Feature freeze |

## Scope cuts (in priority order)

If time runs out, cut from the top of this list first:

1. LLM explainer → ship `templates.py` only
2. What-if box → the chaos panel already demonstrates re-optimization
3. MILP → ship greedy-over-scenarios
4. Supplier finance → keep bank line only
5. Weight sliders → show fixed weights
6. 90-day replay → demo a 30-day window

**Never cut:** Monte Carlo + `deployable_cash`, `rejected_alternatives`, baseline comparison,
the chaos panel.

---

<div align="center">

Built by **Team XYRUS** for **CSI ORIGIN 2026**.

</div>
