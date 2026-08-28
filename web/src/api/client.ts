import type {
  ComparisonMetrics,
  DecisionObject,
  EventInjectResponse,
  Explanation,
  Forecast,
  HelmEvent,
  ObjectiveWeights,
  SimPauseResponse,
  SimPlayResponse,
  SimResetResponse,
  SimStatus,
  SimStepResponse,
  State,
  WeightsResponse,
} from '../types';

import mockState from '../mocks/state.json';
import mockForecast from '../mocks/forecast.json';
import mockForecastCalm from '../mocks/forecastCalm.json';
import mockDecision from '../mocks/decision.json';
import mockDecisionCalm from '../mocks/decisionCalm.json';
import mockDecisionHistory from '../mocks/decisions.json';
import mockExplanation from '../mocks/explanation.json';
import mockExplanationCalm from '../mocks/explanationCalm.json';
import mockEvents from '../mocks/events.json';
import mockComparison from '../mocks/comparison.json';
import mockComparisonCalm from '../mocks/comparisonCalm.json';

// Flip to false once the API is up — every function below then hits `fetch(...)` instead.
export const USE_MOCK = false;

// Real routes are mounted under /api (api/main.py) — the default here already includes it
// so a bare `npm run dev` against a locally-running `uvicorn api.main:app` just works. Point
// VITE_API_BASE at a different host/port (still including /api) to run against anything else.
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api';
// Exported so hooks/useStream.ts can derive `ws(s)://.../api/stream` from the same base
// instead of hardcoding a second host/port to keep in sync with VITE_API_BASE.
export { API_BASE };

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export async function getState(): Promise<State> {
  if (USE_MOCK) return mockState as State;
  return get<State>('/state?policy=AGENT');
}

export async function getForecast(): Promise<Forecast> {
  if (USE_MOCK) return mockForecast as Forecast;
  return get<Forecast>('/forecast?policy=AGENT');
}

// "Calm" variants exist only as a mock-only demo device: the state the page
// loads into before a judge fires a chaos preset. A real backend has no
// separate notion of this — it only ever has "the current state" — so once
// USE_MOCK flips off these just fall through to the normal endpoints.
export async function getForecastCalm(): Promise<Forecast> {
  if (USE_MOCK) return mockForecastCalm as Forecast;
  return get<Forecast>('/forecast?policy=AGENT');
}

// There is no `GET /decision` (singular) in the frozen contract (FINAL.md §10) — only
// `GET /decisions` (history, newest first) and `GET /decisions/{id}`. "The current decision"
// is just the newest AGENT one, so that's what this fetches.
async function getLatestDecision(): Promise<DecisionObject> {
  const rows = await get<DecisionObject[]>('/decisions?policy=AGENT&limit=1');
  if (rows.length === 0) {
    throw new Error('no decisions yet — call POST /sim/reset and /sim/step first');
  }
  return rows[0];
}

export async function getDecision(): Promise<DecisionObject> {
  if (USE_MOCK) return mockDecision as DecisionObject;
  return getLatestDecision();
}

export async function getDecisionCalm(): Promise<DecisionObject> {
  if (USE_MOCK) return mockDecisionCalm as DecisionObject;
  return getLatestDecision();
}

export async function getDecisionHistory(): Promise<DecisionObject[]> {
  if (USE_MOCK) return [...(mockDecisionHistory as DecisionObject[]), mockDecision as DecisionObject];
  return get<DecisionObject[]>('/decisions?policy=AGENT&limit=50');
}

export async function getExplanation(decisionId: string): Promise<Explanation> {
  if (USE_MOCK) {
    // The mock fixtures are per-scenario, not per-ID in general, but we do
    // have two real narratives (calm vs. post-shock) — route between them.
    return decisionId === (mockDecision as DecisionObject).decision_id
      ? (mockExplanation as Explanation)
      : (mockExplanationCalm as Explanation);
  }
  // Frozen contract (FINAL.md §10): POST /explain/{id} with a mode body, not a bare GET.
  // Note: explainer/ is Person C's own router, optionally mounted — until it exists this
  // 404s, same as every other not-yet-built route. Every decision already carries its own
  // `explanation` field (null until the backend's internal call to this same route attaches
  // one), so callers that already have the decision object can read that instead of calling
  // this at all.
  return post<Explanation>(`/explain/${decisionId}`, { mode: 'template' });
}

export async function getEvents(): Promise<HelmEvent[]> {
  if (USE_MOCK) return mockEvents as HelmEvent[];
  return get<HelmEvent[]>('/events?limit=50');
}

export async function getComparison(): Promise<ComparisonMetrics> {
  if (USE_MOCK) return mockComparison as ComparisonMetrics;
  return get<ComparisonMetrics>('/compare');
}

export async function getComparisonCalm(): Promise<ComparisonMetrics> {
  if (USE_MOCK) return mockComparisonCalm as ComparisonMetrics;
  return get<ComparisonMetrics>('/compare');
}

// The Chaos Panel's live wire: POST /events (FINAL.md §10 "Act" table / §8.6 payload table).
// `source` defaults to JUDGE_INJECTED because every caller today is a judge pressing a chaos
// preset button — pass a different one only for a genuinely different origin.
export async function postEvent(
  type: string,
  payload: Record<string, unknown>,
  source = 'JUDGE_INJECTED',
): Promise<EventInjectResponse> {
  return post<EventInjectResponse>('/events', { type, source, payload });
}

// -----------------------------------------------------------------------------------------
// Simulation control (FINAL.md §10 "Simulation control" table). No mock-mode branch here —
// USE_MOCK has no live sim clock to control, so these are only ever called on the real path
// (DashboardPage gates the controls on `!USE_MOCK`).
// -----------------------------------------------------------------------------------------

export async function postSimReset(
  seed?: number,
  startDate?: string,
): Promise<SimResetResponse> {
  const body: Record<string, unknown> = {};
  if (seed !== undefined) body.seed = seed;
  if (startDate !== undefined) body.start_date = startDate;
  return post<SimResetResponse>('/sim/reset', body);
}

export async function postSimStep(days = 1): Promise<SimStepResponse> {
  return post<SimStepResponse>('/sim/step', { days });
}

export async function postSimPlay(days: number, speedMs = 300): Promise<SimPlayResponse> {
  return post<SimPlayResponse>('/sim/play', { days, speed_ms: speedMs });
}

export async function postSimPause(): Promise<SimPauseResponse> {
  return post<SimPauseResponse>('/sim/pause', {});
}

export async function getSimStatus(): Promise<SimStatus> {
  return get<SimStatus>('/sim/status');
}

// POST /weights (FINAL.md §10 "Act" table): the judge-facing weight sliders' live wire —
// re-solves immediately with the new weights and returns the resulting decision.
export async function postWeights(weights: ObjectiveWeights): Promise<WeightsResponse> {
  return post<WeightsResponse>('/weights', weights);
}
