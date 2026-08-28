// state/SimDataProvider.tsx — the live sim data (state/forecast/comparison/decision/events),
// the WS connection, and every sim/weights control handler, lifted above the router.
//
// Why: DashboardPage used to own all of this directly. React Router unmounts a page when you
// navigate away from its route, so leaving /dashboard for /dashboard/history and coming back
// tore down every bit of it — WS included — and refetched from zero, which is the multi-second
// reload flash on every tab switch. Mounting this provider once around <Routes> in App.tsx
// means the data (and the socket) survive navigation; DashboardPage becomes a pure consumer.
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import {
  getComparison,
  getComparisonCalm,
  getDecision,
  getDecisionCalm,
  getEvents,
  getExplanation,
  getForecast,
  getForecastCalm,
  getSimStatus,
  getState,
  postEvent,
  postSimPause,
  postSimPlay,
  postSimReset,
  postSimStep,
  postWeights,
  USE_MOCK,
} from '../api/client';
import type { ChaosPreset } from '../components/ChaosPanel';
import { useStream } from '../hooks/useStream';
import type {
  AgentStatus,
  ComparisonMetrics,
  DecisionObject,
  Explanation,
  Forecast,
  HelmEvent,
  ObjectiveWeights,
  State,
} from '../types';
import { addDaysIso } from '../utils/format';

// api/config.py's own default (HORIZON_DAYS=90) — Play has no "how many days" input in the
// header, so it replays the full horizon by default; POST /sim/pause stops it early at any
// point, and the backend clamps to whatever's left once the horizon is reached either way.
const PLAY_HORIZON_DAYS = 90;
const PLAY_SPEED_MS = 300;

// Builds the real POST /events payload for one chaos preset from the *current* live state —
// the frozen payload shapes (FINAL.md §8.6) need the world's current value to compute the
// delta (old_apr_pct, old_liquidity_stress, the receivable's current expected_date), which
// only the loaded State has. Returns null if the preset's target isn't in the current world
// (e.g. the seed changed, or the demo re-fires a preset whose target is already resolved).
function buildEventRequest(
  preset: ChaosPreset,
  state: State,
): { type: string; payload: Record<string, unknown> } | null {
  switch (preset.id) {
    case 'ashwin-late': {
      const rcv = state.receivables.find((r) => r.id === preset.target);
      if (!rcv) return null;
      return {
        type: 'RECEIVABLE_DELAYED',
        payload: {
          receivable_id: rcv.id,
          new_expected_date: addDaysIso(rcv.expected_date, 21),
          delay_days: 21,
        },
      };
    }
    case 'rate-jump': {
      const fac = state.facilities.find((f) => f.id === preset.target);
      if (!fac) return null;
      return {
        type: 'RATE_CHANGE',
        payload: { facility_id: fac.id, old_apr_pct: fac.apr_pct, new_apr_pct: 18.0 },
      };
    }
    case 'gst-notice':
      return {
        type: 'NEW_OBLIGATION',
        payload: {
          obligation_id: `OBL-GST-${state.sim_day}`,
          label: 'Emergency GST notice',
          amount: 900000,
          due_date: addDaysIso(state.as_of, 5),
          category: 'TAX',
        },
      };
    case 'supplier-distress': {
      const sup = state.suppliers.find((s) => s.id === preset.target);
      if (!sup) return null;
      return {
        type: 'SUPPLIER_DISTRESS',
        payload: {
          supplier_id: sup.id,
          old_liquidity_stress: sup.liquidity_stress,
          new_liquidity_stress: 0.85,
        },
      };
    }
    default:
      return null;
  }
}

// Events can arrive from two paths at once for the same POST /events call — the response
// body and the "event" WS frame it also broadcasts — so every event append goes through here
// rather than a bare spread, keyed on the frozen `event_id`.
function mergeEvents(prev: HelmEvent[] | null, incoming: HelmEvent[]): HelmEvent[] {
  const merged = prev ? [...prev] : [];
  const seen = new Set(merged.map((e) => e.event_id));
  for (const event of incoming) {
    if (!seen.has(event.event_id)) {
      merged.push(event);
      seen.add(event.event_id);
    }
  }
  return merged;
}

export interface SimData {
  state: State | null;
  forecast: Forecast | null;
  comparison: ComparisonMetrics | null;
  decision: DecisionObject | null;
  events: HelmEvent[] | null;
  explanation: Explanation | null;
  explanationOpen: boolean;
  agentStatus: AgentStatus;
  flippedTargetIds: Set<string>;
  hasShocked: boolean;
  simRunning: boolean;
  controlsBusy: boolean;
  // No backend route returns metrics *history* (GET /compare is always "right now" —
  // FINAL.md §10) — this is client-observed only, one entry per distinct sim_day seen on
  // the "metrics" WS channel or a direct GET /compare, since the page opened. Good enough to
  // scrub a replay of *this session's* run; a hard refresh starts it over. Sorted by sim_day.
  metricsHistory: ComparisonMetrics[];
  closeExplanation: () => void;
  handleExplain: () => void;
  handleStep: () => void;
  handlePlayPause: () => void;
  handleReset: () => void;
  handleWeightsCommit: (weights: ObjectiveWeights) => void;
  handleChaosFire: (preset: ChaosPreset) => void;
}

const SimDataContext = createContext<SimData | null>(null);

let syntheticEventCounter = 0;

export function SimDataProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [comparison, setComparison] = useState<ComparisonMetrics | null>(null);
  const [decision, setDecision] = useState<DecisionObject | null>(null);
  const [events, setEvents] = useState<HelmEvent[] | null>(null);

  const [explanation, setExplanation] = useState<Explanation | null>(null);
  const [explanationOpen, setExplanationOpen] = useState(false);

  const [agentStatus, setAgentStatus] = useState<AgentStatus>('RUNNING');
  const [flippedTargetIds, setFlippedTargetIds] = useState<Set<string>>(new Set());

  const [hasShocked, setHasShocked] = useState(false);

  const [metricsHistory, setMetricsHistory] = useState<ComparisonMetrics[]>([]);
  // Every call site that learns a new ComparisonMetrics (initial load, a WS "metrics" frame,
  // a direct refetch after Step/Weights) goes through here instead of a bare `setComparison`,
  // upserting it into the replay history by sim_day in the same update rather than a separate
  // effect watching `comparison` — the same day can legitimately recompute more than once (a
  // manual /decide, a weights change), and the replay should show that day's latest figure,
  // not a duplicate point.
  const recordComparison = (cm: ComparisonMetrics) => {
    setComparison(cm);
    setMetricsHistory((prev) => {
      const idx = prev.findIndex((m) => m.sim_day === cm.sim_day);
      const next = idx === -1 ? [...prev, cm] : prev.map((m, i) => (i === idx ? cm : m));
      return next.sort((a, b) => a.sim_day - b.sim_day);
    });
  };

  // Sim clock controls (Header's Step/Play-Pause/Reset buttons, POST /sim/* — FINAL.md §10).
  // `simRunning` mirrors the backend's `sim_state.running` flag; `controlsBusy` covers the
  // round trip of whichever control is in flight so a second click can't race it.
  const [simRunning, setSimRunning] = useState(false);
  const [controlsBusy, setControlsBusy] = useState(false);

  useEffect(() => {
    // Runs exactly once, on first mount of the provider (App.tsx, above the router) — not on
    // every tab switch. Against the real backend this 404s until POST /sim/reset (+ at least
    // one /sim/step) has run once — every setter below is already null-safe (EmptyState
    // pattern, CLAUDE.md rule 9), so a cold-start 404 just leaves the page in its loading
    // state instead of throwing into the console unhandled.
    getState().then(setState).catch(console.error);
    getForecastCalm().then(setForecast).catch(console.error);
    getComparisonCalm().then(recordComparison).catch(console.error);
    getDecisionCalm().then(setDecision).catch(console.error);
    getEvents().then(setEvents).catch(console.error);
    if (!USE_MOCK) {
      getSimStatus()
        .then((s) => setSimRunning(s.running))
        .catch(console.error);
    }
  }, []);

  // Shared by the chaos flow and the WS "decision" channel: swap in a new decision and, if
  // it flipped anything from the previous one, pulse those action cards amber for 3s (HELM.md
  // §5 step 4).
  const applyDecisionFrame = (newDecision: DecisionObject) => {
    setDecision(newDecision);
    const flippedIds = new Set(
      newDecision.diff_from_previous.flipped.map((f) => f.target_id),
    );
    if (flippedIds.size > 0) {
      setFlippedTargetIds(flippedIds);
      window.setTimeout(() => setFlippedTargetIds(new Set()), 3000);
    }
  };

  // WS /api/stream (FINAL.md §10 "WebSocket") — live updates while the sim clock runs via
  // Play, plus a general safety net for anything broadcast outside of this tab's own request
  // (another judge's browser, a curl'd POST /events, etc). Mounted once here (not per-page),
  // so it stays connected across tab switches instead of reconnecting on every navigation.
  // Disabled in mock mode: USE_MOCK has no live backend to connect to.
  useStream(
    {
      onSim: (data) => {
        setSimRunning(data.running);
        // Neither "sim" nor "metrics"/"forecast" (already handled below) carry the full
        // State — invoices, cash_available, obligations — so a day advancing means refetching
        // it directly rather than waiting on a channel that doesn't exist.
        getState().then(setState).catch(console.error);
      },
      onForecast: (data) => setForecast(data),
      onMetrics: (data) => recordComparison(data),
      onDecision: (data) => {
        if (data.policy !== 'AGENT') return; // the scoreboard reads BASELINE from /compare, not the queue
        applyDecisionFrame(data);
      },
      onEvent: (data) => setEvents((prev) => mergeEvents(prev, [data])),
      onLog: (data) => {
        // sim_runner.py's own text for "the replay ended on its own, not via pause" (section
        // 3) — the only signal a finished /sim/play gives that isn't a "sim" frame.
        if (data.level === 'warn' || data.text.includes('finished')) setSimRunning(false);
      },
    },
    !USE_MOCK,
  );

  const handleStep = async () => {
    if (USE_MOCK || controlsBusy || simRunning) return;
    setControlsBusy(true);
    try {
      const result = await postSimStep(1);
      if (result.events.length > 0) setEvents((prev) => mergeEvents(prev, result.events));
      const latestAgentDecision = [...result.decisions]
        .reverse()
        .find((d) => d.policy === 'AGENT');
      if (latestAgentDecision) applyDecisionFrame(latestAgentDecision);
      // /sim/step's response carries only events/decisions (FINAL.md §10) — cash, invoice
      // status and the forecast/scoreboard all need a direct refetch.
      const [newState, newForecast, newComparison] = await Promise.all([
        getState(),
        getForecast(),
        getComparison(),
      ]);
      setState(newState);
      setForecast(newForecast);
      recordComparison(newComparison);
    } catch (err) {
      console.error('sim/step failed', err);
    } finally {
      setControlsBusy(false);
    }
  };

  const handlePlayPause = async () => {
    if (USE_MOCK || controlsBusy) return;
    setControlsBusy(true);
    try {
      if (simRunning) {
        await postSimPause();
        setSimRunning(false);
      } else {
        await postSimPlay(PLAY_HORIZON_DAYS, PLAY_SPEED_MS);
        setSimRunning(true);
      }
    } catch (err) {
      console.error('sim play/pause failed', err);
    } finally {
      setControlsBusy(false);
    }
  };

  const handleReset = async () => {
    if (USE_MOCK || controlsBusy) return;
    setControlsBusy(true);
    try {
      await postSimReset();
      setSimRunning(false);
      setHasShocked(false);
      setFlippedTargetIds(new Set());
      setAgentStatus('RUNNING');
      setExplanation(null);
      setExplanationOpen(false);
      // A fresh world has no decisions until the first /sim/step — clear rather than show a
      // stale one from before the reset (getDecision() would 404 on an empty history).
      setDecision(null);
      // A fresh world restarts sim_day at 0 — last run's metrics history would otherwise
      // sit at higher sim_days than anything new coming in, corrupting the replay chart.
      setMetricsHistory([]);
      const [newState, newForecast, newComparison, newEvents] = await Promise.all([
        getState(),
        getForecast(),
        getComparison(),
        getEvents(),
      ]);
      setState(newState);
      setForecast(newForecast);
      recordComparison(newComparison);
      setEvents(newEvents);
    } catch (err) {
      console.error('sim/reset failed', err);
    } finally {
      setControlsBusy(false);
    }
  };

  const handleWeightsCommit = async (weights: ObjectiveWeights) => {
    if (USE_MOCK || controlsBusy) return;
    setControlsBusy(true);
    try {
      const { decision: newDecision } = await postWeights(weights);
      applyDecisionFrame(newDecision);
      getComparison().then(recordComparison).catch(console.error);
    } catch (err) {
      console.error('weights update failed', err);
    } finally {
      setControlsBusy(false);
    }
  };

  const handleExplain = () => {
    if (!decision) return;
    setExplanationOpen(true);
    if (!explanation || explanation.decision_id !== decision.decision_id) {
      getExplanation(decision.decision_id)
        .then(setExplanation)
        .catch((err) => {
          console.error('explanation unavailable', err);
          setExplanation(null);
        });
    }
  };

  // Steps 3 + 6 of HELM.md §5: the fan chart redraws and KPIs settle on post-shock values —
  // not just a card pulse and a log line. Shared by both the mock and live paths below.
  const applyShock = (
    shockedForecast: Forecast,
    shockedComparison: ComparisonMetrics,
    shockedDecision: DecisionObject,
    event: HelmEvent,
  ) => {
    setForecast(shockedForecast);
    recordComparison(shockedComparison);
    applyDecisionFrame(shockedDecision);
    setHasShocked(true);
    setEvents((prev) => mergeEvents(prev, [event]));
    setAgentStatus('RUNNING');
  };

  const handleChaosFire = (preset: ChaosPreset) => {
    if (agentStatus === 'RE-OPTIMIZING' || hasShocked) return;

    setAgentStatus('RE-OPTIMIZING');

    window.setTimeout(async () => {
      try {
        if (USE_MOCK) {
          // Mock mode has no live engine: swap in the pre-baked "shocked" fixtures rather
          // than posting anything.
          const [shockedForecast, shockedComparison, shockedDecision] = await Promise.all([
            getForecast(),
            getComparison(),
            getDecision(),
          ]);
          syntheticEventCounter += 1;
          applyShock(shockedForecast, shockedComparison, shockedDecision, {
            event_id: `EVT-DEMO-${syntheticEventCounter}`,
            sim_day: shockedDecision.sim_day,
            date: shockedDecision.run_at,
            type: preset.eventType,
            source: 'JUDGE_INJECTED',
            payload: { target: preset.target, raw: preset.payload },
            materiality_score: 0.42,
            triggered_reoptimization: true,
            triggered_decision_id: shockedDecision.decision_id,
          });
          return;
        }

        if (!state) return;
        const request = buildEventRequest(preset, state);
        if (!request) {
          console.error(`chaos preset ${preset.id}: target not found in the current state`);
          setAgentStatus('RUNNING');
          return;
        }

        // POST /events (FINAL.md §10) confirms the event landed and, if material, kicks off
        // re-optimization synchronously — decision comes back in the same response. It does
        // NOT return the new forecast/comparison, so those two are refetched separately, per
        // the frontend brief's own plan.
        const { event, decision: triggeredDecision } = await postEvent(
          request.type,
          request.payload,
        );
        const [shockedForecast, shockedComparison, latestDecision] = await Promise.all([
          getForecast(),
          getComparison(),
          triggeredDecision ? Promise.resolve(triggeredDecision) : getDecision(),
        ]);
        applyShock(shockedForecast, shockedComparison, latestDecision, event);
      } catch (err) {
        console.error('chaos event failed', err);
        setAgentStatus('RUNNING');
      }
    }, 1100);
  };

  const value: SimData = {
    state,
    forecast,
    comparison,
    decision,
    events,
    explanation,
    explanationOpen,
    agentStatus,
    flippedTargetIds,
    hasShocked,
    simRunning,
    controlsBusy,
    metricsHistory,
    closeExplanation: () => setExplanationOpen(false),
    handleExplain,
    handleStep,
    handlePlayPause,
    handleReset,
    handleWeightsCommit,
    handleChaosFire,
  };

  return <SimDataContext.Provider value={value}>{children}</SimDataContext.Provider>;
}

export function useSimData(): SimData {
  const ctx = useContext(SimDataContext);
  if (!ctx) throw new Error('useSimData() called outside <SimDataProvider>');
  return ctx;
}
