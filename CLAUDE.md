# CLAUDE.md — HELM (Team XYRUS)

Read `PROJECT.md` for architecture, contracts, ownership map, and role instructions.
That file is the single source of truth. This file holds only the rules that never change.

## Project

Autonomous working-capital management agent. CSI ORIGIN 2026, PS-4, 24-hour build.
Monorepo: `contracts/`, `engine/`, `api/`, `explainer/`, `web/`.

## Non-negotiable rules

1. **Stay in your own folder.** `engine/` is Shyam. `api/` is Person B. `explainer/` and `web/` are Person C. Never edit outside your folder — say it out loud instead. This is what prevents merge conflicts.
2. **Contracts are frozen at H+1.** Build against `contracts/fixtures/*.json`, never against another person's running code. Any contract change is announced out loud and logged in `contracts/CHANGELOG.md`.
3. **The engine is a pure function of `State`.** No database, no env vars, no network, no stdout. Dicts/Pydantic models in, dicts out.
4. **The LLM never computes a number.** The optimiser decides; the explainer only narrates a decision that already exists, using figures handed to it in the `DecisionObject`. No exceptions.
5. **The engine emits `reason_code` enums, never prose.** English is generated in `explainer/` only.
6. **Deterministic output.** Seed the RNG from `(sim_day, decision_id)`. The same state must produce the same decision every time, or the demo flickers.
7. **Never let a solve hang.** Hard 2-second timeout, then greedy fallback with `solver.fallback_used = true`.
8. **Never show a raw enum in the UI.** Every `reason_code`, `action_type`, and `event_type` must pass through the `REASON_TEXT` / `ACTION_TEXT` / `EVENT_TEXT` lookup maps in `web/src/utils/reason.ts`. If a new enum value is added to `contracts/enums.py`, the lookup map must be updated in the same commit.
9. **Every component must survive null data.** Use the `<EmptyState>` pattern. A white screen during a demo is a dead demo. The API will be broken at some point tonight.
10. **Indian rupee formatting everywhere.** Use `inr()` from `web/src/utils/format.ts`. Display as `₹42,00,000` (Indian locale), never `₹4,200,000`. Lakhs and crores for large numbers.

## Git

- Branches: `feat/engine`, `feat/api`, `feat/web`. `main` is merged only at checkpoints.
- `git add <your-folder>` — never `git add -A` or `git add .` from the root.
- **Do not run `git add`, `git commit`, or `git push` on my behalf.** I stage, commit and push manually on every project. Show me the commands or the diff instead.

## Code conventions

- Python: `ruff format`, type hints on all public functions, Pydantic for anything crossing a boundary.
- TypeScript: `snake_case` in all JSON and API types to match the Python contracts. Do not camelCase payload fields.
- Money is rupees as float, rounded to 2 decimals at the API boundary only. Never compare money with `==`.
- Dates are ISO `"YYYY-MM-DD"` strings. Time is `sim_day` (int, starts at 0). No timezones anywhere.

## Key contracts to remember

- `ComparisonMetrics` includes `health_score` (0–100 int) and `savings_per_day` (float) for both AGENT and BASELINE policies, plus deltas. `health_score` is computed by `api/`, not the engine.
- `DecisionObject.actions[]` covers **every** open invoice — a HOLD is explicit, never inferred from absence.
- `DecisionObject.actions[].rejected_alternatives[]` has at least one entry per action. This is PS requirement 7.
- `Explanation.would_change_if` is the judge magnet. Render it distinctly.
- `Forecast.deployable_cash` is THE number. It is what makes this project not a dashboard.

## Frontend architecture (Person C)

- Single page, no routing. Everything visible without navigation.
- Layout: header → KPI strip (7 cards) → two-column (fan chart + scoreboard left, decision queue + timeline right) → bottom panel (chaos + sliders).
- Shared utilities built at H+1 before any component: `web/src/utils/format.ts` (inr, bps, pct, simDate) and `web/src/utils/reason.ts` (REASON_TEXT, ACTION_TEXT, ACTION_COLOR, EVENT_TEXT).
- `USE_MOCK` flag in `web/src/api/client.ts` — build everything on fixtures first, flip one env var when the API is up.
- Recharts for the fan chart. No other chart library.
- Dark theme. One accent colour. Monospace for numbers. No animation over 300ms.

## Chaos panel presets (hardcoded for demo)

| Button | Event type | Target | Payload |
|---|---|---|---|
| Ashwin Motors pays 3 weeks late | `RECEIVABLE_DELAYED` | `RCV-0004` | `delay_days: 21` |
| Bank rate jumps to 18% | `RATE_CHANGE` | `FAC-001` | `new_apr_pct: 18.0` |
| Emergency GST notice ₹9L in 5 days | `NEW_OBLIGATION` | — | `amount: 900000, category: TAX` |
| Meenakshi Steels in distress | `SUPPLIER_DISTRESS` | `SUP-001` | `new_liquidity_stress: 0.85` |

Preset #1 is the demo script moment at 2:00. Judge should never need to fill a form.

## Shock sequence (what happens when a chaos event fires)

1. Agent status → `⟳ RE-OPTIMIZING` (amber) — immediate
2. KPI strip greys out — 50ms
3. Fan chart redraws with new bands — on WebSocket `forecast` frame
4. Flipped decisions pulse amber border — 3 seconds
5. ActivityTimeline scrolls in new entries with materiality score
6. KPIs and health score update to post-shock values
7. Agent status → `● RUNNING` (green)

All transitions under 300ms. This sequence is the entire demo.

## Checkpoints

H+8 state→forecast→decide end to end. **H+12 one invoice through the entire pipeline including the LLM narrative.** H+16 full 90-day replay, agent vs baseline. H+19 feature freeze.

## Scope cuts (in order — cut from top)

1. LLM explainer → ship `templates.py` only
2. What-if box → chaos panel already demos re-optimisation
3. MILP → ship greedy-over-scenarios
4. Supplier finance → keep bank line only
5. Weight sliders → show fixed weights
6. 90-day replay → demo 30-day window

**Never cut:** Monte Carlo + deployable_cash, rejected_alternatives, baseline comparison, chaos panel.

## The pitch in one line

"A company's treasurer decides every morning where limited cash goes. He does it with static rules, and those rules break the moment a customer pays late. We replaced him."
