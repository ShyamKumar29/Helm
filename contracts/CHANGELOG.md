# contracts/ changelog

Every contract change (schemas.py, enums.py) is logged here: hour, who, what.

---

- **H+? (session 2026-08-28), Person B (backend session, on Shyam's account)** —
  Created `contracts/` from scratch: `enums.py`, `schemas.py`, `fixtures/*.json`. This
  package did not exist in the checkout (B2's report flagged this as a blocker for B3).
  Content is a verbatim transcription of the frozen shapes already agreed in `FINAL.md`
  section 8 — no new fields, no renamed fields, no shape decisions made here. Confirmed
  out loud with the user (acting for Shyam/all three) before writing, per
  `docs/backend/01-OWNERSHIP-AND-CONFLICT-RULES.md` section 2.1.

- **2026-08-29 (integration verification session, on Shyam's account)** — Data fix, not a
  shape change: `contracts/fixtures/forecast.sample.json` had only 2 `buckets` entries
  (`day_offset` 0 and 30). FINAL.md §8.3 is explicit — "`buckets` has exactly
  `horizon_days + 1` entries, one per day" — so this fixture violated its own frozen spec
  since the H+1 session above. Nothing enforces the count in `contracts/schemas.py`
  (`Forecast.buckets: list[ForecastBucket]`, no length validator), so it validated fine and
  the bug was invisible until the dashboard was run against it live: with only 2 points,
  `CashFanChart` draws one straight line segment for the entire 90-day fan, and since
  `engine/` isn't in this checkout every `/forecast` call returns this same static fixture
  regardless of `sim_day` — so the chart never changed shape while every other KPI moved.
  Regenerated to the full 91 daily buckets. `day_offset` 0 and 30 keep their exact original
  values (`p10`/`p50`/`p90`/`shortfall_prob`/`committed_outflow`/`expected_inflow`) — every
  other field at the top level (`deployable_cash`, `buffer_required`, `binding_date`,
  `binding_reason`, `worst_case_min_cash`) is untouched. The added days are a smoothstep
  interpolation: day0→day30 unchanged (still the original 2-point shape over that span),
  day30→day90 a plausible partial recovery with a widening P10/P90 band, consistent with
  `binding_reason`'s "payroll, with RCV-0001 collecting late" story. Re-validated against
  `contracts.schemas.Forecast`. No field renamed, no field added/removed, no schema change —
  logged here per CLAUDE.md rule 2 because it's still a `contracts/` edit.
