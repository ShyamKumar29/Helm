import type {
  ComparisonMetrics,
  DecisionObject,
  Explanation,
  Forecast,
  HelmEvent,
  State,
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
export const USE_MOCK = true;

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json() as Promise<T>;
}

export async function getState(): Promise<State> {
  if (USE_MOCK) return mockState as State;
  return get<State>('/state');
}

export async function getForecast(): Promise<Forecast> {
  if (USE_MOCK) return mockForecast as Forecast;
  return get<Forecast>('/forecast');
}

// "Calm" variants exist only as a mock-only demo device: the state the page
// loads into before a judge fires a chaos preset. A real backend has no
// separate notion of this — it only ever has "the current state" — so once
// USE_MOCK flips off these just fall through to the normal endpoints.
export async function getForecastCalm(): Promise<Forecast> {
  if (USE_MOCK) return mockForecastCalm as Forecast;
  return get<Forecast>('/forecast');
}

export async function getDecision(): Promise<DecisionObject> {
  if (USE_MOCK) return mockDecision as DecisionObject;
  return get<DecisionObject>('/decision');
}

export async function getDecisionCalm(): Promise<DecisionObject> {
  if (USE_MOCK) return mockDecisionCalm as DecisionObject;
  return get<DecisionObject>('/decision');
}

export async function getDecisionHistory(): Promise<DecisionObject[]> {
  if (USE_MOCK) return [...(mockDecisionHistory as DecisionObject[]), mockDecision as DecisionObject];
  return get<DecisionObject[]>('/decisions');
}

export async function getExplanation(decisionId: string): Promise<Explanation> {
  if (USE_MOCK) {
    // The mock fixtures are per-scenario, not per-ID in general, but we do
    // have two real narratives (calm vs. post-shock) — route between them.
    return decisionId === (mockDecision as DecisionObject).decision_id
      ? (mockExplanation as Explanation)
      : (mockExplanationCalm as Explanation);
  }
  return get<Explanation>(`/explanation/${decisionId}`);
}

export async function getEvents(): Promise<HelmEvent[]> {
  if (USE_MOCK) return mockEvents as HelmEvent[];
  return get<HelmEvent[]>('/events');
}

export async function getComparison(): Promise<ComparisonMetrics> {
  if (USE_MOCK) return mockComparison as ComparisonMetrics;
  return get<ComparisonMetrics>('/comparison');
}

export async function getComparisonCalm(): Promise<ComparisonMetrics> {
  if (USE_MOCK) return mockComparisonCalm as ComparisonMetrics;
  return get<ComparisonMetrics>('/comparison');
}
