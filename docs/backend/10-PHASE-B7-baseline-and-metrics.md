# Phase B7 — Baseline Agent and Comparison Metrics

**Window:** H+13 → H+16
**Unblocks:** the scoreboard, checkpoint I4

---

## 1. Goal

A deliberately simple baseline agent running on the BASELINE world, and `ComparisonMetrics`
with `health_score` and `savings_per_day` for both policies.

`FINAL.md` section 4: *"A dumb baseline running in parallel that visibly loses. This is the
single highest-scoring artefact we can build."*

## 2. Files

```
api/baseline/__init__.py
api/baseline/static_rules.py   # the agent
api/services/metrics.py        # ComparisonMetrics, health score, savings per day
api/routers/compare.py         # GET /compare — real now
```

## 3. The baseline agent

Exactly `FINAL.md` section 11.8. Do not improve it. Do not add a forecast. Do not add supplier
awareness. Its whole value is that it is **what a real finance team actually does**, and it
must be recognisably that, or beating it means nothing.

```python
RESERVE = Decimal("500000")     # fixed ₹5,00,000 cash reserve, no forecasting

def run(session, sim) -> dict:
    cash = latest_balance(session, "BASELINE")
    actions = []
    for inv in open_invoices(session, "BASELINE"):
        if inv.discount_until == sim.as_of and cash > inv.amount:
            actions.append(act(inv, "PAY_EARLY_DISCOUNT", funding="CASH"))
        elif inv.due_date == sim.as_of:
            if cash - RESERVE >= inv.amount:
                actions.append(act(inv, "PAY_AT_MATURITY", funding="CASH"))
            else:
                actions.append(act(inv, "FINANCE_BANK", funding="BANK_LINE"))
        else:
            actions.append(act(inv, "HOLD", funding=None))
    return decision_object(actions, policy="BASELINE", sim=sim)
```

### It must emit the same shape

`FINAL.md` section 8.4: *"`policy` is `"AGENT"` or `"BASELINE"`. Both agents emit the same
shape so the frontend can render either."* So the baseline's output is a full
`DecisionObject` that validates against the same Pydantic model, including:

- an action for **every** open invoice, `HOLD` included
- **at least one `rejected_alternatives` entry per action** — PS requirement 7 applies to the
  baseline too, if only so the frontend never crashes on an empty array
- `solver: {"method": "GREEDY_FALLBACK", "status": "FEASIBLE", "solve_ms": 0, "n_scenarios": 0, "fallback_used": false}`
- `deployable_cash` = `max(0, cash - RESERVE)` — the baseline's naive idea of a floor, which
  is exactly the point
- `diff_from_previous` filled the same way

For a baseline action, the rejected alternative is honest and simple: the action the rule did
not take, with `reason_code: "NO_BETTER_ALTERNATIVE"` and `delta: 0.0`. Do not fabricate a
`net_value` the baseline never computed — the baseline does not score, and pretending it does
is the kind of thing a finance-literate judge catches.

### Where it must visibly lose

If these three do not show up in the replay, the seed data needs retuning (phase B2), not the
baseline:

1. **Missed discounts** during a temporary cash dip — the `cash > invoice.amount` test fails
   on a day the agent would have borrowed at 13.5% to capture 37.2%.
2. **Over-borrowing near payroll** — no forecast, so it draws the bank line at maturity
   instead of having reserved cash.
3. **A missed payroll** when the large receivable slips — `shortfall_days > 0` and
   `obligations_missed >= 1`.

## 4. ComparisonMetrics

Shape frozen in `FINAL.md` section 8.7. Computed per policy from the ledger and the invoice
table — never from the decisions, because a proposed decision is not an outcome.

| Field | Source |
|---|---|
| `discounts_captured` | sum of `discount_captured` across `INVOICE_PAID` events for that policy |
| `financing_cost` | sum of ledger rows with reason `INTEREST` |
| `penalties_paid` | sum of ledger rows with reason `PENALTY` |
| `net_working_capital_cost` | `financing_cost + penalties_paid - discounts_captured` |
| `shortfall_days` | count of distinct `sim_day` where the closing balance was `< 0` |
| `min_cash_seen` | `min(balance)` over the whole ledger for that policy |
| `obligations_missed` | obligations whose due date passed with the balance going negative |
| `avg_supplier_stress` | mean `liquidity_stress` weighted by outstanding invoice amount |
| `decisions_made` | count of `decisions` rows for that policy |
| `reoptimizations_triggered` | count of decisions with `trigger.type == "EVENT"` |
| `health_score` | formula below |
| `savings_per_day` | `-net_working_capital_cost / max(sim_day, 1)` |

`delta` carries `net_working_capital_cost`, `shortfall_days`, `obligations_missed`,
`health_score` — each computed as `agent - baseline`.

**`net_working_capital_cost` lower is better and negative is excellent.** The scoreboard
headline is `delta.net_working_capital_cost`, which should be a large negative number.

### Health score

Implement `FINAL.md` section 8.7 exactly:

```python
def health_score(m, sim_day, total_obligations, total_payable_value, total_discount_available) -> int:
    v = (100
         - 30 * (m.shortfall_days / max(sim_day, 1))
         - 20 * (m.obligations_missed / max(total_obligations, 1))
         - 15 * (m.penalties_paid / max(1, total_payable_value)) * 100
         - 15 * (1 - m.discounts_captured / max(1, total_discount_available))
         - 10 * m.avg_supplier_stress
         - 10 * (m.financing_cost / max(1, total_payable_value)) * 100)
    return int(round(max(0.0, min(100.0, v))))
```

Notes that will save you a confusing hour:

- The formula is written against `sim_day`, so at `sim_day = 0` the first term divides by
  zero. `max(sim_day, 1)` — do it once, here.
- `total_payable_value`, `total_obligations` and `total_discount_available` are **world
  constants**, computed once at seed time and cached on `sim_state`. Recomputing them each
  tick makes health drift for reasons nobody can explain on stage.
- Clamp to `[0, 100]` and return an `int`. Person C colour-bands it: 80+ green, 50–79 amber,
  <50 red.

If the agent's health score is not visibly above the baseline's by mid-replay, that is a seed
data problem. Retune in B2 with Shyam, not by adjusting the formula. The formula is in the
contract; adjusting it to flatter the agent is exactly the thing that falls apart under
questioning.

## 5. `GET /compare`

Compute both policies, assemble, validate against the Pydantic model, return. Also broadcast
the identical object on the `metrics` channel after step 8 of every simulated day — Person C
updates every KPI card from that frame.

Cache the computed metrics on the `sim_state` row after each day so `GET /compare` is a single
row read. The 90-day replay calls it once per day and the aggregate queries are the slowest
thing in the loop.

## 6. Definition of done

- [ ] The baseline runs every day on the BASELINE world and persists a `DecisionObject`
- [ ] Baseline output validates against the same Pydantic model as the agent's
- [ ] Every baseline action has at least one `rejected_alternatives` entry
- [ ] `GET /compare` returns a validated `ComparisonMetrics`
- [ ] `health_score` is an int in `[0, 100]` for both policies, no divide-by-zero at day 0
- [ ] `net_working_capital_cost = financing_cost + penalties_paid - discounts_captured` holds exactly
- [ ] After a 90-day replay: agent beats baseline on `net_working_capital_cost`,
      `shortfall_days` and `obligations_missed`
- [ ] `metrics` frames arrive on the socket every simulated day
- [ ] The three baseline failure modes are visible in the replay

## 7. Verify

```bash
curl -s -X POST localhost:8000/api/sim/reset -H 'content-type: application/json' \
  -d '{"seed":42,"start_date":"2026-03-01"}'
curl -s -X POST localhost:8000/api/sim/step -H 'content-type: application/json' -d '{"days":90}' > /dev/null

curl -s localhost:8000/api/compare > /tmp/cmp.json
python - <<'PY'
import json
from contracts.schemas import ComparisonMetrics
c = json.load(open("/tmp/cmp.json"))
ComparisonMetrics.model_validate(c)
a, b = c["agent"], c["baseline"]
for k in ("agent", "baseline"):
    m = c[k]
    lhs = round(m["net_working_capital_cost"], 2)
    rhs = round(m["financing_cost"] + m["penalties_paid"] - m["discounts_captured"], 2)
    assert abs(lhs - rhs) < 0.01, (k, lhs, rhs)
    assert 0 <= m["health_score"] <= 100
print("nwc  agent", a["net_working_capital_cost"], " baseline", b["net_working_capital_cost"])
print("short", a["shortfall_days"], b["shortfall_days"],
      "| missed", a["obligations_missed"], b["obligations_missed"],
      "| health", a["health_score"], b["health_score"])
assert a["net_working_capital_cost"] < b["net_working_capital_cost"], "agent does not win — retune seed"
print("agent wins by", round(b["net_working_capital_cost"] - a["net_working_capital_cost"], 2))
PY
```

That last assertion is the checkpoint I4 gate. If it fails, the problem is the seed data.
