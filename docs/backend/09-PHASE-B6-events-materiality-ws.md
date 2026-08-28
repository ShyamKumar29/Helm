# Phase B6 — Events, Materiality, WebSocket

**Window:** H+10 → H+13 (overlaps B5 deliberately)
**Unblocks:** the chaos panel — which is the entire live demo

---

## 1. Goal

`POST /api/events` accepts a judge-injected event, applies it to the world, scores its
materiality, re-optimises if it clears the threshold, and returns both the event and the
resulting decision. `WS /api/stream` pushes six channels to the dashboard.

`FINAL.md` section 13: *"This endpoint is the demo. It must be bulletproof."*

## 2. Files

```
api/services/materiality.py    # the score from section 11.7
api/services/ws.py             # connection hub + broadcast
api/services/event_apply.py    # one applier per event type
api/routers/events.py          # POST /events (GET already done in B3)
```

## 3. Materiality — `FINAL.md` section 11.7

```
materiality = |Δ deployable_cash| / max(cash_available, 1)
              + 0.5 × |Δ P(any shortfall in horizon)|
              + 1.0 if feasibility of any hard obligation changed
```

Implementation, exactly:

1. Forecast **before** applying the event → `deployable_before`, `shortfall_prob_before`,
   `feasible_before`
2. Apply the event to the world
3. Forecast **after** → `deployable_after`, `shortfall_prob_after`, `feasible_after`
4. Score

That is two engine forecast calls per injected event. At the engine's 400ms target that is
800ms, which is inside the demo's tolerance. If it is not, the fallback is to reuse the newest
decision's `deployable_cash` as the "before" value — say it out loud so Shyam knows you are
doing it.

`P(any shortfall in horizon)` = `max(bucket.shortfall_prob for bucket in forecast.buckets)`.
Simple, defensible, and it moves when it should.

"Feasibility of a hard obligation changed" = for any `hard` obligation, whether its due-date
P90 bucket balance crossed zero in either direction.

**Log both outcomes.** The declined line is worth points:

```
"Event EVT-0031 materiality 0.42 >= threshold 0.15 - re-optimising"
"Event EVT-0032 materiality 0.03 < threshold 0.15 - no change needed"
```

Threshold comes from `config.MATERIALITY_THRESHOLD`, default 0.15. Do not hardcode it.

## 4. `POST /api/events`

Body is an `Event` **without** `event_id` and `materiality_score` — the server assigns both.

```
1. validate type is in the frozen EventType enum        -> 400 if not
2. validate payload shape for that type (section 8.6)    -> 422 if not
3. assign event_id = EVT-{n:04d}; date/sim_day from sim_state
4. persist the event row
5. broadcast on channel "event"
6. forecast-before, apply, forecast-after, score materiality
7. persist materiality_score on the event row
8. broadcast a "log" frame with the threshold comparison
9. if material: build state, decide, validate, persist, attach explanation,
   broadcast on "decision" and "forecast"
10. recompute metrics, broadcast on "metrics"
11. return {"event": {...}, "decision": {...} | null}
```

Return shape is frozen in section 10: `{"event": Event, "decision": DecisionObject | null}`.
`decision` is `null` when the event was immaterial. Person C's chaos panel handles both.

### Payload appliers

One small function per event type, keyed off the frozen payload shapes in section 8.6. Apply
to **both policies** where the event is about the outside world:

| Event | Applies to | Effect |
|---|---|---|
| `RECEIVABLE_DELAYED` | shared | set `receivables.expected_date = new_expected_date`; clear any cached realised arrival |
| `RATE_CHANGE` | both policies | `facilities.apr_pct = new_apr_pct` on both policy rows |
| `NEW_OBLIGATION` | shared | insert an obligation row |
| `SUPPLIER_DISTRESS` | shared | `suppliers.liquidity_stress = new_liquidity_stress` |
| `CASH_INJECTION` | both policies | ledger row per policy |
| `NEW_INVOICE` | both policies | insert one invoice row per policy, identical |

**`RATE_CHANGE` and `CASH_INJECTION` must hit both policy rows.** A rate that only rises for
the agent is a rigged comparison, and a sharp judge will ask.

Unknown event type, or a payload missing a required key: `400`/`422` in the error envelope.
Never accept a half-valid event — a malformed event that half-applies is unrecoverable
mid-demo without a reset.

### Bulletproofing

- Wrap every applier in a transaction; roll back the whole event on any failure.
- Never let a failed re-optimise fail the event. If `decide()` degrades, return the event with
  `decision: null` and a log frame saying so. The judge still sees the fan chart move.
- Idempotence is not required (a judge firing the same shock twice legitimately shocks twice),
  but the second firing must not error.

## 5. WebSocket — `WS /api/stream`

Frozen envelope, section 10:

```json
{ "channel": "decision", "sim_day": 12, "data": { } }
```

Channels: `event`, `decision`, `metrics`, `forecast`, `sim`, `log`.

```python
# api/services/ws.py
class Hub:
    def __init__(self):
        self._conns: set[WebSocket] = set()

    async def connect(self, ws):
        await ws.accept(); self._conns.add(ws)

    def disconnect(self, ws):
        self._conns.discard(ws)

    async def send(self, channel: str, sim_day: int, data: dict):
        frame = {"channel": channel, "sim_day": sim_day, "data": data}
        dead = []
        for ws in list(self._conns):
            try:
                await ws.send_json(frame)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

hub = Hub()
```

Rules:

- **A dead socket never raises into a request handler.** Collect and drop, as above. Person C
  will reload the page fifty times tonight and every reload leaves a stale connection.
- **On connect, send a snapshot**: current `sim` frame, newest `metrics` frame, newest
  `forecast` frame. Otherwise a mid-demo reload shows an empty dashboard until the next tick,
  which looks broken.
- **`log` frames carry `{"level": "info"|"warn", "text": "..."}`.** Text is human-readable and
  goes straight into the ActivityTimeline. This is the one place `api/` writes English, and it
  is fine — it is operational logging, not decision rationale.
- Broadcast is fire-and-forget. Never await a client.

### What gets broadcast when

| Trigger | Channels |
|---|---|
| day advanced | `sim`, then `event` per event |
| decision persisted | `decision`, `forecast` |
| metrics recomputed | `metrics` |
| materiality checked | `log` (both outcomes) |
| engine degraded / fallback used | `log` at `warn` |
| action escalated | `log` at `warn` |

The shock sequence in `CLAUDE.md` depends on `forecast` arriving before `metrics`. Broadcast
in that order.

## 6. Definition of done

- [ ] `POST /api/events` with each of the four chaos presets works end to end
- [ ] Preset #1 (`RCV-0004`, `delay_days: 21`) produces materiality above threshold and a
      decision whose `diff_from_previous.flipped` is non-empty
- [ ] A deliberately trivial event scores below threshold, returns `decision: null`, and emits
      the "no change needed" log frame
- [ ] Malformed payload returns 422 in the envelope and changes nothing in the DB
- [ ] `RATE_CHANGE` updates both policy rows
- [ ] WebSocket delivers all six channels; a client reload gets a snapshot immediately
- [ ] Killing and reconnecting a client does not raise anywhere in the API
- [ ] Person C confirms the full shock sequence renders

## 7. Verify

```bash
# preset 1 — the demo moment
curl -s -X POST localhost:8000/api/events -H 'content-type: application/json' -d '{
  "type":"RECEIVABLE_DELAYED","source":"JUDGE_INJECTED",
  "payload":{"receivable_id":"RCV-0004","new_expected_date":"2026-04-03","delay_days":21}
}' | python -c "import json,sys; r=json.load(sys.stdin); e=r['event']; d=r['decision']; \
print('materiality', e['materiality_score']); \
print('flipped', len(d['diff_from_previous']['flipped']) if d else 'no decision')"

# preset 2
curl -s -X POST localhost:8000/api/events -H 'content-type: application/json' -d '{
  "type":"RATE_CHANGE","source":"JUDGE_INJECTED",
  "payload":{"facility_id":"FAC-001","old_apr_pct":13.5,"new_apr_pct":18.0}}' > /dev/null
docker compose exec -T db psql -U helm -d helm -c \
  "select policy, apr_pct from facilities where id='FAC-001';"   # both rows 18.0

# malformed
curl -s -X POST localhost:8000/api/events -H 'content-type: application/json' \
  -d '{"type":"RECEIVABLE_DELAYED","source":"JUDGE_INJECTED","payload":{}}' | grep -q '"error"' \
  && echo "envelope ok"

# socket
python - <<'PY'
import asyncio, json, websockets
async def m():
    async with websockets.connect("ws://localhost:8000/api/stream") as ws:
        for _ in range(3):
            f = json.loads(await ws.recv()); print(f["channel"], f["sim_day"])
asyncio.run(m())
PY
```

`flipped` being empty on preset #1 means the seed data is not dramatic enough. That is a B2
problem, not a B6 problem — go back and retune with Shyam.
