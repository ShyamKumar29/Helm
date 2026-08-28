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
- [Known gaps](#known-gaps)
- [Engineering rules](#engineering-rules)
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
                 │  contracts/ │   Pydantic models — frozen, single source of truth
                 └──────┬──────┘   for every shape crossing a boundary
                        │
         ┌──────────────┼───────────────┐
         │              │               │
   ┌─────▼─────┐  ┌─────▼─────┐  ┌──────▼──────┐
   │  engine/  │  │   api/    │  │ explainer/  │
   │           │  │           │  │             │
   │ Pure fn:  │  │ FastAPI + │  │ template.py │
   │ State →   │  │ Postgres, │  │ (required)  │
   │ Forecast  │  │ sim clock,│  │ + llm.py    │
   │ → Decision│  │ WS stream │  │ (Groq)      │
   │           │  │           │  │             │
   │ Monte     │  │ Never     │  │ Never       │
   │ Carlo +   │  │ imports   │  │ computes a  │
   │ MILP/     │  │ engine/   │  │ number —    │
   │ greedy    │  │ or        │  │ HTTP-only   │
   │           │  │ explainer/│  │ self-calls  │
   │ No DB, no │  │ outside a │  │ back into   │
   │ network,  │  │ try/except│  │ api/, never │
   │ no stdout │  │           │  │ a Python    │
   │           │  │           │  │ import      │
   └───────────┘  └─────┬─────┘  └─────────────┘
                        │ REST + WebSocket
                  ┌─────▼─────┐
                  │   web/    │   Single-page dashboard, dark instrument-panel UI.
                  │           │   Live tab + Replay (scrub any sim day) + History + About.
                  │           │   USE_MOCK flag: build against fixtures, flip one variable
                  │           │   for the live API. One shared SimDataProvider holds state
                  │           │   + the WS connection above the router so tab switches
                  │           │   don't refetch from zero.
                  └───────────┘
```

**The engine is a pure function of `State`.** Dicts/Pydantic models in, dicts out — no database,
no environment variables, no network calls, no stdout. Given the same `State`, it produces the
same decision every time (seeded off a stable hash of the state's own content).

**Every layer degrades gracefully.** `api/` boots green with `engine/` or `explainer/` missing or
broken — both imports are wrapped in `try/except`, falling back to a fixture or a 404. This is
what let three people build in parallel from hour one, and it's still true today with all three
layers real.

## Repository layout

```
Helm/
├── CLAUDE.md               # Non-negotiable project rules (this file never changes)
├── FINAL.md                # Full architecture spec, contracts, and role instructions —
│                            # the single source of truth for everything below
├── contracts/               # Pydantic models + frozen TS-mirrored fixtures, shared by all
│   ├── schemas.py            # source of truth for every shape crossing a boundary
│   ├── enums.py               # frozen enums (ActionType, ReasonCode, EventType, ...)
│   ├── CHANGELOG.md           # every contract edit, logged
│   └── fixtures/               # sample State/Forecast/DecisionObject/... JSON
│
├── engine/                  # Pure decision engine — owned by Shyam
│   ├── decide.py              # the only public contract: forecast() and decide()
│   ├── rng.py                  # deterministic seeding off a hash of State
│   ├── forecast/                # Monte Carlo, delay mixture model, liquidity floor
│   ├── actions/                  # candidate (action, funding_source) generation per invoice
│   ├── optimizer/                  # scoring formulas, scenario MILP (PuLP/CBC), greedy fallback
│   ├── diffing/                     # decision_diff — what flipped since the last decision, and why
│   └── tests/                        # pytest — shape + coverage + determinism checks
│
├── api/                     # FastAPI backend — owned by Person B
│   ├── main.py                # all routers mounted, frozen after H+1
│   ├── models.py                # SQLAlchemy ORM — Postgres, append-only cash_ledger
│   ├── routers/                   # state, sim, decisions, events, compare (+ WS /stream)
│   ├── services/                    # state_builder, sim_loop, materiality, metrics, ws hub, ...
│   ├── baseline/                      # the deliberately-simple static-rules comparison agent
│   └── seed/                           # deterministic seeded world generator
│
├── explainer/                # LLM narration layer — never imports api/
│   ├── router.py               # POST /explain/{id}, POST /whatif
│   ├── templates.py             # required, deterministic, no API key
│   ├── llm.py                     # Groq-backed enhancement, numeric-grounding checked
│   └── whatif.py                    # non-destructive what-if scenario compare
│
├── web/                      # React dashboard — owned by Person C
│   └── src/
│       ├── state/SimDataProvider.tsx  # live state + WS connection, mounted once above the router
│       ├── hooks/useStream.ts           # the one WebSocket client (/api/stream)
│       ├── pages/                         # DashboardPage (Live), ReplayPage, HistoryPage, AboutPage
│       ├── components/                      # Header, KpiStrip, CashFanChart, DecisionQueue, ...
│       ├── utils/                             # format.ts (inr, simDate), reason.ts (enum → text)
│       └── api/client.ts                       # USE_MOCK flag + every typed API call
│
├── docs/backend/              # the backend build track — phase-by-phase, Person B's own plan
└── scripts/                    # reset.sh and verification scripts
```

## Ownership map

| Folder | Owner | Rule |
|---|---|---|
| `engine/` | Shyam | Never edited outside by others |
| `api/` | Person B | Never edited outside by others |
| `explainer/`, `web/` | Person C | Never edited outside by others |
| `contracts/` | Shared | Frozen — any change is announced and logged in `contracts/CHANGELOG.md` |

Branches: `feat/engine` → merged into `feat/api` → merged into `feat/web`. `feat/web` is the
integration branch everyone pulls from.

## Data contracts

All contract field names are `snake_case` and frozen — never camelCased on the frontend, even
though the UI layer is TypeScript. The core shapes (full definitions in `contracts/schemas.py`
and `web/src/types.ts`):

| Contract | Purpose |
|---|---|
| `State` | Ground truth as of a given `sim_day`: cash, suppliers, customers, invoices, receivables, obligations, facilities |
| `Forecast` | 90-day Monte Carlo cash projection — `p10`/`p50`/`p90` buckets, `deployable_cash`, `buffer_required`, `binding_date` |
| `DecisionObject` | One decision run: an `actions[]` entry for **every** open invoice, each with `rejected_alternatives[]` and a `reason_code` enum |
| `Explanation` | Narrative for a `DecisionObject` — headline, prose, assumptions, trade-offs, `would_change_if[]` |
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

Verified live: the **Emergency GST notice** preset genuinely re-optimizes — `deployable_cash`
drops by exactly ₹9,00,000 and real invoices flip from `PAY_EARLY_DISCOUNT` to `HOLD` to protect
the tax payment. The **Ashwin Motors** preset currently produces a materiality score below the
re-optimization threshold on the seeded data — see [Known gaps](#known-gaps).

## Tech stack

| Layer | Choice |
|---|---|
| **Backend** | FastAPI, SQLAlchemy, Postgres 16, Pydantic v2 |
| **Engine** | NumPy (vectorized Monte Carlo), PuLP + CBC (scenario MILP) |
| **Explainer** | `httpx` → Groq's OpenAI-compatible endpoint (`openai/gpt-oss-120b`) for the LLM-mode narrative; a fully deterministic template mode needs no API key at all |
| **Frontend build** | Vite |
| **Frontend framework** | React 19 + TypeScript |
| **Styling** | Tailwind CSS |
| **Charts** | Recharts (fan chart with P10/P50/P90 bands, Replay's health-over-time chart) |
| **Animation** | Framer Motion |
| **Icons** | lucide-react + hand-drawn SVGs (`HelmWheel`, `CompassRose`) |
| **Fonts** | Geist Sans / Geist Mono (self-hosted via Fontsource) for instrument/numeric content, Fraunces italic for narrative text |
| **Live updates** | Native WebSocket (`web/src/hooks/useStream.ts`) — one client, auto-reconnecting |
| **Testing** | `pytest` (`engine/tests/`) |

## Getting started

### 1. Database

```bash
docker compose up -d db
```

(If Docker isn't available, any Postgres 16 instance works — just point `DATABASE_URL` at it.)

### 2. Backend

```bash
python -m venv .venv && source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r api/requirements.txt -r engine/requirements.txt -r explainer/requirements.txt

cp .env.example .env
# GROQ_API_KEY is optional — leave it blank to use the deterministic template explainer.
# Everything else in .env.example already has a working default.

uvicorn api.main:app --reload --port 8000
```

### 3. Reset the simulation

```bash
curl -X POST localhost:8000/api/sim/reset \
  -H 'content-type: application/json' \
  -d '{"seed": 42, "start_date": "2026-03-01"}'
```

Or just use the **Reset** button in the dashboard header once the frontend is up.

### 4. Frontend

```bash
cd web
npm install
npm run dev
```

Open `http://localhost:5173/dashboard`. `USE_MOCK` in `web/src/api/client.ts` is `false` by
default, pointed at `http://localhost:8000/api` — set `VITE_API_BASE` (see `web/.env.example`)
if your backend runs somewhere else.

Other useful commands (run from `web/`):

```bash
npm run build     # tsc -b && vite build — production build
npm run lint       # oxlint
npm run preview    # preview a production build locally
```

Backend tests:

```bash
python -m pytest engine/tests/ -q
```

## Project status

**Everything is built and verified live** — not fixture-mocked, not simulated-as-a-placeholder.

- **`contracts/`** — every shape, all fixtures, `CHANGELOG.md` up to date.
- **`engine/`** — real Monte Carlo forecast (NumPy, vectorized), real liquidity floor, real
  scenario MILP (PuLP/CBC, 5 percentile scenarios, hard time cap) with the mandated greedy
  fallback, real decision diffing. `pytest engine/tests/` passes: shape validation, every-invoice
  coverage, determinism, diff correctness.
- **`api/`** — all 16 contract routes real (`/sim/*`, `/state`, `/forecast`, `/decisions`,
  `/events`, `/compare`, `/decide`, `/weights`, WS `/stream`), Postgres-backed, append-only
  ledger, both `AGENT` and `BASELINE` policies running in parallel. Boots green with `engine/`
  or `explainer/` missing (verified — both drills passed).
- **`explainer/`** — `templates.py` (required floor) and `llm.py` (Groq, with a numeric-grounding
  check that discards and falls back to the template if the model ever cites an unlisted number).
  `/whatif` runs a full non-destructive scenario comparison.
- **`web/`** — every panel built and wired to the real backend: KPI strip, cash fan chart,
  decision queue with rejected-alternatives disclosure, scoreboard, activity timeline, chaos
  panel, weight sliders (`POST /weights` re-solves live), and Step/Play/Pause/Reset controls
  actually driving the sim clock. A live WebSocket connection keeps everything current during
  `/sim/play`. A **Replay** tab lets you scrub any simulated day and see its events, decisions,
  and health-score trend correlated on one screen.

## Known gaps

Two things found during integration testing, both understood, neither fixed yet:

1. **The Ashwin Motors chaos preset doesn't currently flip anything.** The engine does react to
   receivable delays (confirmed — a different receivable moved the materiality score), but this
   specific preset's numbers land below the re-optimization threshold on today's seed data.
   This is the seed-data tuning pass `FINAL.md` §12 explicitly calls out as required, separate
   work — not an engine bug. Lives in `api/seed/`.
2. **`POST /sim/step` over many days is slower than the ~250ms/day budget** (roughly 5s/day
   measured). Root cause: `api/services/sim_loop.py`'s explanation-attach step makes a
   self-referential HTTP call back into the same single-process async server while that request
   is still in flight, stalling ~3s per decision before timing out. Doesn't affect correctness,
   does affect how usable `/sim/play`'s live replay feels for a long run. One-line-ish fix
   (run the blocking day-advance in a thread, or make the self-call properly async) — flagged,
   not applied, since it touches `api/`.

## Engineering rules

The full list lives in `CLAUDE.md`; the ones that shape every contribution:

1. **Stay in your own folder.** Cross-folder edits happen by conversation, not by commit.
2. **Contracts are frozen.** Build against `contracts/fixtures/*.json`, never against another
   person's running code, without announcing the change and logging it.
3. **The engine is a pure function of `State`.** No database, no env vars, no network, no stdout.
4. **The LLM never computes a number.** It only narrates a decision that already exists, and
   every number it writes has to trace back to a field it was actually given.
5. **The engine emits `reason_code` enums, never prose.**
6. **Deterministic output** — the same `State` produces the same decision, every time.
7. **Never let a solve hang** — hard time budget, then a greedy fallback with
   `solver.fallback_used = true`.
8. **Never show a raw enum in the UI** — every enum passes through a `*_TEXT` lookup map, updated
   in the same commit that adds the enum value.
9. **Every component must survive null data** — the `<EmptyState>` pattern, everywhere.
10. **Indian rupee formatting everywhere** — `inr()` renders `₹42,00,000`, lakhs and crores, never
    `₹4,200,000`.

## Scope cuts (in priority order)

`FINAL.md`'s original cut list, for reference — and what actually shipped against it:

| Cut | Shipped? |
|---|---|
| 1. LLM explainer → ship `templates.py` only | **Not cut** — both `templates.py` and Groq-backed `llm.py` shipped |
| 2. What-if box → chaos panel alone is enough | **Not cut** — `POST /whatif` is real, non-destructive |
| 3. MILP → ship greedy-over-scenarios | **Not cut** — real scenario MILP (PuLP/CBC) shipped, greedy kept as the permanent fallback per spec |
| 4. Supplier finance → bank line only | **Not cut** — `FINANCE_SUPPLIER` is a real candidate action |
| 5. Weight sliders → fixed weights | **Not cut** — sliders re-solve live against the real backend |
| 6. 90-day replay → 30-day window | **Not cut** — full 90-day horizon, plus a scrubbable Replay tab |

**Never cut, and didn't need to be:** Monte Carlo + `deployable_cash`, `rejected_alternatives`,
baseline comparison, the chaos panel.

---

<div align="center">

Built by **Team XYRUS** for **CSI ORIGIN 2026**.

</div>
