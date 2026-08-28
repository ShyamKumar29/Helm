import { motion } from 'framer-motion';
import { Pause, Play } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import {
  Area,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getDecisionHistory, USE_MOCK } from '../api/client';
import { AmbientBackground } from '../components/AmbientBackground';
import { AnimatedNumber } from '../components/AnimatedNumber';
import { EmptyState } from '../components/EmptyState';
import { Header } from '../components/Header';
import { CompassRose } from '../components/icons/CompassRose';
import { Panel } from '../components/Panel';
import { useSimData } from '../state/SimDataProvider';
import type { DecisionObject, HelmEvent } from '../types';
import { addDaysIso, simDate } from '../utils/format';
import { fadeUp, hoverLift, staggerContainer, tapPress } from '../utils/motion';
import { ACTION_COLOR, ACTION_TEXT, EVENT_TEXT, REASON_TEXT } from '../utils/reason';

const PILL_CLASSES: Record<string, string> = {
  accent: 'bg-accent-dim text-accent border-accent-dim',
  info: 'bg-info/10 text-info border-info/30',
  warning: 'bg-warning/10 text-warning border-warning/30',
  purple: 'bg-purple/10 text-purple border-purple/30',
  muted: 'bg-border/40 text-text-muted border-border',
};

const AUTOPLAY_INTERVAL_MS = 700;

function healthColor(score: number): string {
  if (score >= 80) return '#2FE0B8';
  if (score >= 50) return '#F0A93E';
  return '#FF5C5C';
}

interface ChartPoint {
  sim_day: number;
  agent_health: number;
  baseline_health: number;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: { payload: ChartPoint }[];
}) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-2 text-xs font-mono tabular-nums shadow-lg">
      <div className="mb-1 text-text-secondary">Day {point.sim_day}</div>
      <div className="text-accent">Agent {Math.round(point.agent_health)}/100</div>
      <div className="text-danger">Baseline {Math.round(point.baseline_health)}/100</div>
    </div>
  );
}

// One row per event on the scrubbed day.
function EventRow({ event }: { event: HelmEvent }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-border/50 py-2.5 last:border-b-0">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-sm text-text-primary">{EVENT_TEXT[event.type] ?? event.type}</span>
        <span className="font-mono text-[11px] tabular-nums text-text-muted">
          {event.event_id}
          {event.triggered_decision_id && ` · triggered ${event.triggered_decision_id}`}
        </span>
      </div>
      <span className="shrink-0 font-mono text-[11px] tabular-nums text-text-muted">
        {event.materiality_score !== null ? `materiality ${event.materiality_score.toFixed(2)}` : 'n/a'}
      </span>
    </div>
  );
}

// One card per decision made on the scrubbed day (mirrors HistoryPage's card, condensed).
function ReplayDecisionCard({ decision }: { decision: DecisionObject }) {
  return (
    <div className="flex flex-col gap-3 rounded-lg border border-border bg-panel/60 px-4 py-3.5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs font-semibold tabular-nums text-text-primary">
            {decision.decision_id}
          </span>
          <span className="rounded-pill border border-border bg-panel px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-text-muted">
            {decision.policy}
          </span>
        </div>
        <span className="font-mono text-sm font-semibold tabular-nums text-accent">
          {decision.objective_value.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
        </span>
      </div>
      <p className="voice-narrative text-xs text-text-secondary">{decision.trigger.description}</p>
      <div className="flex flex-col gap-1.5">
        {decision.actions.map((action) => {
          const color = ACTION_COLOR[action.action] ?? 'muted';
          return (
            <div key={action.action_id} className="flex flex-wrap items-center justify-between gap-2 text-xs">
              <div className="flex min-w-0 items-center gap-2">
                <span
                  className={`shrink-0 rounded-pill border px-1.5 py-0.5 font-mono text-[9.5px] font-semibold uppercase tracking-wider ${PILL_CLASSES[color]}`}
                >
                  {ACTION_TEXT[action.action] ?? action.action}
                </span>
                <span className="truncate text-text-muted">
                  {REASON_TEXT[action.primary_reason_code] ?? action.primary_reason_code}
                </span>
              </div>
              <span className="shrink-0 font-mono tabular-nums text-text-secondary">
                {action.amount.toLocaleString('en-IN', { maximumFractionDigits: 0 })}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ReplayPage() {
  const {
    state,
    agentStatus,
    simRunning,
    controlsBusy,
    handleStep,
    handlePlayPause,
    handleReset,
    events,
    decision,
    metricsHistory,
  } = useSimData();

  const [decisions, setDecisions] = useState<DecisionObject[] | null>(null);
  // Raw slider position, clamped to `maxDay` (derived below) at read time rather than via a
  // separate effect — `maxDay` shrinking (e.g. right after Reset) just makes the clamped
  // value fall automatically, no extra render-cascade needed.
  const [rawScrubDay, setRawScrubDay] = useState(0);
  const [autoPlaying, setAutoPlaying] = useState(false);

  // Refetches whenever a new decision lands (context's `decision` changes) so a day you Step
  // into while sitting on this tab shows up without a manual reload.
  useEffect(() => {
    getDecisionHistory().then(setDecisions).catch(console.error);
  }, [decision?.decision_id]);

  // The furthest day we have anything to show for, from every source at once — there's no
  // single "give me the timeline" route, so this is a client-side union of what's already
  // been fetched/streamed (FINAL.md §10 has no history endpoint for /compare, only "now").
  const maxDay = useMemo(() => {
    let max = 0;
    for (const e of events ?? []) max = Math.max(max, e.sim_day);
    for (const d of decisions ?? []) max = Math.max(max, d.sim_day);
    for (const m of metricsHistory) max = Math.max(max, m.sim_day);
    if (state) max = Math.max(max, state.sim_day);
    return max;
  }, [events, decisions, metricsHistory, state]);

  const scrubDay = Math.min(rawScrubDay, maxDay);

  useEffect(() => {
    if (!autoPlaying) return undefined;
    if (scrubDay >= maxDay) {
      setAutoPlaying(false);
      return undefined;
    }
    const t = window.setTimeout(() => setRawScrubDay(scrubDay + 1), AUTOPLAY_INTERVAL_MS);
    return () => window.clearTimeout(t);
  }, [autoPlaying, scrubDay, maxDay]);

  const dayEvents = (events ?? [])
    .filter((e) => e.sim_day === scrubDay)
    .sort((a, b) => a.event_id.localeCompare(b.event_id));
  const dayDecisions = (decisions ?? []).filter((d) => d.sim_day === scrubDay);

  // Date for the scrubbed day: prefer an exact match from whatever landed on that day,
  // otherwise offset from the earliest metrics point we have (normally sim_day 0 — the
  // reset's own as_of).
  const scrubDate = useMemo(() => {
    const exact =
      dayEvents[0]?.date ??
      dayDecisions[0]?.run_at ??
      metricsHistory.find((m) => m.sim_day === scrubDay)?.as_of;
    if (exact) return exact;
    const base = metricsHistory[0];
    return base ? addDaysIso(base.as_of, scrubDay - base.sim_day) : '';
  }, [dayEvents, dayDecisions, metricsHistory, scrubDay]);

  const chartData: ChartPoint[] = metricsHistory.map((m) => ({
    sim_day: m.sim_day,
    agent_health: m.agent.health_score,
    baseline_health: m.baseline.health_score,
  }));

  const scrubMetrics = metricsHistory.find((m) => m.sim_day === scrubDay);
  const agentHealthAtScrub = scrubMetrics?.agent.health_score ?? null;
  const baselineHealthAtScrub = scrubMetrics?.baseline.health_score ?? null;
  const tickInterval = Math.max(1, Math.floor(chartData.length / 10));

  return (
    <div className="relative flex min-h-screen flex-col bg-page">
      <AmbientBackground />
      <Header
        status={agentStatus}
        simDay={state?.sim_day ?? 0}
        asOf={state?.as_of ?? ''}
        onStep={USE_MOCK ? undefined : handleStep}
        onPlayPause={USE_MOCK ? undefined : handlePlayPause}
        onReset={USE_MOCK ? undefined : handleReset}
        simRunning={simRunning}
        controlsBusy={controlsBusy}
      />

      <motion.main
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-4 p-6"
      >
        <motion.div variants={fadeUp}>
          <h1 className="text-xl font-semibold text-text-primary">Replay</h1>
          <p className="text-sm text-text-secondary">
            Scrub through every day of this run — events, the decision(s) made, and
            agent-vs-baseline health, correlated on one screen.
          </p>
        </motion.div>

        {chartData.length === 0 ? (
          <motion.div variants={fadeUp} className="rounded-card border border-border bg-panel">
            <EmptyState text="Nothing to replay yet — Step or Play the simulation on Live first." />
          </motion.div>
        ) : (
          <>
            {/* Hero scrubber — same treatment as the Live tab's fan chart (ambient glow,
                compass watermark, big animated number) so Replay reads as part of the same
                product instead of a bolted-on debug view. */}
            <motion.div
              variants={fadeUp}
              className="relative flex flex-col gap-5 overflow-hidden rounded-card border border-border bg-hero p-5"
            >
              <motion.div
                aria-hidden
                className="pointer-events-none absolute -left-20 -top-20 h-72 w-72 rounded-full bg-accent/10 blur-3xl"
                animate={{ x: [0, 40, -10, 0], y: [0, 25, 10, 0] }}
                transition={{ duration: 18, repeat: Infinity, ease: 'easeInOut' }}
              />
              <CompassRose className="pointer-events-none absolute -bottom-16 -right-16 h-64 w-64 text-accent/[0.06]" />

              <div className="relative flex flex-wrap items-start justify-between gap-4">
                <div>
                  <span className="label-caps inline-flex items-center gap-1.5">
                    <motion.span
                      className="h-1.5 w-1.5 rounded-full bg-accent"
                      animate={{ opacity: [1, 0.35, 1], scale: [1, 1.3, 1] }}
                      transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
                    />
                    Health on day {scrubDay}
                  </span>
                  <div className="flex items-baseline gap-3">
                    <span
                      className="font-mono text-4xl font-semibold tabular-nums text-text-primary"
                      style={{ color: agentHealthAtScrub !== null ? healthColor(agentHealthAtScrub) : undefined }}
                    >
                      {agentHealthAtScrub !== null ? (
                        <AnimatedNumber value={agentHealthAtScrub} format={(v) => `${Math.round(v)}`} />
                      ) : (
                        '—'
                      )}
                    </span>
                    <span className="font-mono text-sm text-text-muted">/ 100 agent</span>
                    {baselineHealthAtScrub !== null && (
                      <span className="rounded-pill border border-danger/30 bg-danger/10 px-2 py-0.5 font-mono text-xs tabular-nums text-danger">
                        baseline {Math.round(baselineHealthAtScrub)}
                      </span>
                    )}
                  </div>
                  <p className="voice-narrative mt-1 max-w-md text-[15px] leading-snug text-text-secondary">
                    {scrubDate ? simDate(scrubDate) : `Day ${scrubDay}`}
                    {dayDecisions.length > 0 && ` · ${dayDecisions.length} decision(s)`}
                    {dayEvents.length > 0 && ` · ${dayEvents.length} event(s)`}
                  </p>
                </div>

                <div className="flex items-center gap-2 rounded-pill border border-border bg-panel/60 px-2 py-1.5">
                  <span className="flex items-center gap-1.5 font-mono text-[11px] text-text-muted">
                    <span className="h-1.5 w-1.5 rounded-full bg-accent" /> agent
                  </span>
                  <span className="flex items-center gap-1.5 font-mono text-[11px] text-text-muted">
                    <span className="h-1.5 w-2 rounded-full border border-dashed border-danger" /> baseline
                  </span>
                </div>
              </div>

              <div className="relative h-52 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="replayHealthFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#2FE0B8" stopOpacity={0.28} />
                        <stop offset="100%" stopColor="#2FE0B8" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <XAxis
                      dataKey="sim_day"
                      interval={tickInterval}
                      tickFormatter={(d: number) => `D${d}`}
                      tick={{ fill: '#56635F', fontSize: 11, fontFamily: 'Geist Mono, monospace' }}
                      axisLine={{ stroke: '#1C242B' }}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fill: '#56635F', fontSize: 11, fontFamily: 'Geist Mono, monospace' }}
                      axisLine={false}
                      tickLine={false}
                      width={32}
                    />
                    <Tooltip content={<ChartTooltip />} />
                    <ReferenceLine y={80} stroke="#2FE0B8" strokeOpacity={0.2} strokeDasharray="2 3" />
                    <ReferenceLine y={50} stroke="#F0A93E" strokeOpacity={0.2} strokeDasharray="2 3" />
                    <ReferenceLine
                      x={scrubDay}
                      stroke="#F0A93E"
                      strokeDasharray="3 3"
                      label={{ value: 'now', position: 'insideTopRight', fill: '#F0A93E', fontSize: 10 }}
                    />
                    <Area
                      dataKey="agent_health"
                      stroke="#2FE0B8"
                      strokeWidth={2}
                      fill="url(#replayHealthFill)"
                      isAnimationActive
                      animationDuration={500}
                      animationEasing="ease-out"
                    />
                    <Line
                      dataKey="baseline_health"
                      stroke="#FF5C5C"
                      strokeWidth={1.75}
                      strokeDasharray="4 3"
                      dot={false}
                      isAnimationActive
                      animationDuration={500}
                      animationEasing="ease-out"
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              <div className="relative flex items-center gap-3">
                <motion.button
                  type="button"
                  onClick={() => setAutoPlaying((v) => !v)}
                  disabled={maxDay === 0}
                  aria-label={autoPlaying ? 'Pause replay' : 'Play replay'}
                  whileHover={maxDay === 0 ? undefined : hoverLift}
                  whileTap={maxDay === 0 ? undefined : tapPress}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-accent-dim bg-accent-dim/40 text-accent transition-colors duration-150 hover:bg-accent-dim disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {autoPlaying ? (
                    <Pause size={14} strokeWidth={2} fill="currentColor" />
                  ) : (
                    <Play size={14} strokeWidth={2} fill="currentColor" />
                  )}
                </motion.button>
                <input
                  type="range"
                  min={0}
                  max={maxDay}
                  step={1}
                  value={scrubDay}
                  onChange={(e) => {
                    setAutoPlaying(false);
                    setRawScrubDay(Number(e.target.value));
                  }}
                  className="h-1.5 w-full cursor-pointer appearance-none rounded-pill bg-border accent-[#2FE0B8]"
                />
                <span className="w-20 shrink-0 text-right font-mono text-xs tabular-nums text-text-secondary">
                  Day {scrubDay}/{maxDay}
                </span>
              </div>
              <p className="relative text-[11px] text-text-muted">
                Built from what this browser has observed live this session — no backend route
                returns metrics history, only "right now" (GET /compare). Step or Play to extend it.
              </p>
            </motion.div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Panel title={`Events — day ${scrubDay}`} className="h-80">
                <div className="no-scrollbar flex h-full flex-col overflow-y-auto px-1">
                  {dayEvents.length === 0 ? (
                    <EmptyState text="No events this day." />
                  ) : (
                    dayEvents.map((e) => <EventRow key={e.event_id} event={e} />)
                  )}
                </div>
              </Panel>

              <Panel title={`Decisions — day ${scrubDay}`} className="h-80">
                <div className="no-scrollbar flex h-full flex-col gap-3 overflow-y-auto px-1">
                  {dayDecisions.length === 0 ? (
                    <EmptyState text="No decision recorded this day." />
                  ) : (
                    dayDecisions.map((d) => <ReplayDecisionCard key={d.decision_id} decision={d} />)
                  )}
                </div>
              </Panel>
            </div>
          </>
        )}
      </motion.main>
    </div>
  );
}
