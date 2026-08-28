# 02 — The Phase Plan

Nine phases, B0 through B8. Each one leaves the API booting and every route returning a valid
contract shape. There is no phase where the backend is legitimately broken.

---

## 1. The map

| Phase | Name | Window | Unblocks | Doc |
|---|---|---|---|---|
| **B0** | Bootstrap and frozen shell | H+0 → H+1 | Everyone (gitignore, compose); Person C (fixture-backed API) | `03` |
| **B1** | Database and models | H+1 → H+3 | Nothing external; foundation for B2 | `04` |
| **B2** | Seed data | H+3 → H+5 | The whole demo story | `05` |
| **B3** | Read routes on real data | H+5 → H+7 | Person C flips `USE_MOCK=false` | `06` |
| **B4** | State builder + engine gateway | H+7 → H+9 | Shyam gets a real `State` to test against | `07` |
| **B5** | Simulation loop | H+9 → H+12 | Checkpoint I3 — one invoice end to end | `08` |
| **B6** | Events, materiality, WebSocket | H+10 → H+13 | The chaos panel; the entire live demo | `09` |
| **B7** | Baseline agent + metrics | H+13 → H+16 | The scoreboard; checkpoint I4 | `10` |
| **B8** | Hardening, replay, demo support | H+16 → H+19 | The freeze | `11` |

Windows overlap by design. B6 starts while B5 is finishing because the WebSocket hub is
needed by the sim loop's broadcast step, and the two are easier to debug together.

## 2. Mapped onto the project checkpoints

```
H+0 ────── B0 ──────┐
H+1                 │  main.py FROZEN. Fixture API live for Person C.
H+2 ────── B1 ──────┤
H+3                 │
H+4  ◄── CHECKPOINT I1 ──  API boots, docker up, fixtures validate
H+4 ────── B2 ──────┤
H+5                 │
H+6 ────── B3 ──────┤
H+7                 │
H+8  ◄── CHECKPOINT I2 ──  Person C flips USE_MOCK=false, real wiring
H+8 ────── B4 ──────┤
H+9                 │
H+10 ───── B5 ──────┤  (B6 starts in parallel)
H+11                │
H+12 ◄── CHECKPOINT I3 ──  ONE INVOICE END TO END. Everything else stops for this.
H+13 ───── B6 ──────┤
H+14 ───── B7 ──────┤
H+15                │
H+16 ◄── CHECKPOINT I4 ──  90-day replay, scoreboard populated, shock flips a decision
H+17 ───── B8 ──────┤
H+18                │
H+19 ◄── FEATURE FREEZE ──  bugs and demo tuning only
H+20        rehearsals, reset.sh reliability
H+23        buffer
```

## 3. What each phase produces, in one line

- **B0** — a repo everyone can clone safely, and a FastAPI server that answers every route
  from `contracts/fixtures/` with correct shapes.
- **B1** — tables that match `FINAL.md` section 9 exactly, and a session factory.
- **B2** — a world: 40 suppliers, 200 invoices, 8 customers, 60 receivables, obligations,
  two facilities, seeded identically for AGENT and BASELINE, with three planted situations.
- **B3** — `/state`, `/events`, `/decisions`, `/compare` reading Postgres instead of JSON.
- **B4** — `state_builder.py` producing a `State` that validates against `contracts/schemas.py`,
  and the engine gateway with its timeout and fallback.
- **B5** — the eight-step day loop, `/sim/reset|step|status`, decisions persisted, cash ledger
  moving.
- **B6** — `POST /api/events` with materiality gating, and `WS /api/stream` pushing six channels.
- **B7** — the BASELINE world diverging from the AGENT world, and `ComparisonMetrics` with
  `health_score` and `savings_per_day`.
- **B8** — `/sim/play` streaming a 90-day replay, `reset.sh`, error envelope everywhere,
  performance inside budget.

## 4. The single ordering constraint that matters

**B2 (seed data) blocks everything downstream and is the hardest to redo late.**

The three planted situations in the seed are what make the agent look smart. If they are not
there, the scoreboard is boring, the shock does nothing visible, and the demo has no story —
no amount of B7 polish fixes that. Read `13-SEED-DATA-SPEC.md` fully before starting B2, and
budget two hours, not one.

Everything else can be rushed. That cannot.

## 5. If you fall behind

Cut in this order, and only in this order:

1. **`POST /sim/play` streaming.** Replace with the frontend calling `/sim/step` in a loop.
   Loses nothing visible; costs Person C ten lines.
2. **`FINANCE_SUPPLIER` facility (FAC-002).** One flag in the seed generator. Reduces the
   action space and removes a whole class of bug.
3. **`POST /execute/{decision_id}`.** The sim loop already executes scheduled actions; the
   manual route is a convenience.
4. **Real forecast on `/forecast`.** Serve the forecast embedded in the newest decision instead
   of calling the engine again. Halves the load and nobody can tell.
5. **Persisting every daily decision.** Persist only decisions that changed something. The
   timeline still reads correctly from the log frames.

**Never cut:** the cash ledger, the policy split, materiality gating, or the error envelope.
Those four are what make the system explainable when a judge asks a hard question, and they
are also what makes it debuggable at hour 20.

## 6. Phase file structure

Every phase file has the same five sections, so you can skim one at 3am:

1. **Goal** — one paragraph
2. **Files** — exactly what you create or edit
3. **Build steps** — numbered, in order
4. **Definition of done** — a checklist
5. **Verify** — a command that proves it
