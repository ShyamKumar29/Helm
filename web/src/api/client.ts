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
import mockDecision from '../mocks/decision.json';
import mockExplanation from '../mocks/explanation.json';
import mockEvents from '../mocks/events.json';
import mockComparison from '../mocks/comparison.json';

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

export async function getDecision(): Promise<DecisionObject> {
  if (USE_MOCK) return mockDecision as DecisionObject;
  return get<DecisionObject>('/decision');
}

export async function getExplanation(decisionId: string): Promise<Explanation> {
  if (USE_MOCK) return mockExplanation as Explanation;
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
