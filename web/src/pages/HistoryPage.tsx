import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { getDecisionHistory, USE_MOCK } from '../api/client';
import { AmbientBackground } from '../components/AmbientBackground';
import { EmptyState } from '../components/EmptyState';
import { Header } from '../components/Header';
import { useSimData } from '../state/SimDataProvider';
import type { DecisionObject, State } from '../types';
import { inr, simDate } from '../utils/format';
import { fadeUp, staggerContainer } from '../utils/motion';
import { ACTION_COLOR, ACTION_TEXT, REASON_TEXT } from '../utils/reason';

const PILL_CLASSES: Record<string, string> = {
  accent: 'bg-accent-dim text-accent border-accent-dim',
  info: 'bg-info/10 text-info border-info/30',
  warning: 'bg-warning/10 text-warning border-warning/30',
  purple: 'bg-purple/10 text-purple border-purple/30',
  muted: 'bg-border/40 text-text-muted border-border',
};

function DecisionCard({ decision, state }: { decision: DecisionObject; state: State | null }) {
  return (
    <motion.div
      variants={fadeUp}
      className="flex flex-col gap-4 rounded-card border border-border bg-panel px-5 py-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-sm font-semibold tabular-nums text-text-primary">
              {decision.decision_id}
            </span>
            <span className="rounded-pill border border-border bg-panel/60 px-2 py-0.5 font-mono text-[10.5px] uppercase tracking-wider text-text-muted">
              {decision.policy}
            </span>
          </div>
          <span className="font-mono text-[11px] tabular-nums text-text-muted">
            Day {decision.sim_day} · {simDate(decision.run_at)}
          </span>
        </div>
        <div className="text-right">
          <span className="label-caps">Objective value</span>
          <div className="font-mono text-lg font-semibold tabular-nums text-accent">
            {inr(decision.objective_value)}
          </div>
        </div>
      </div>

      <p className="voice-narrative text-sm text-text-secondary">{decision.trigger.description}</p>

      <div className="flex flex-col gap-2 border-t border-border/60 pt-3">
        {decision.actions.map((action) => {
          const supplier = state?.suppliers.find((s) => s.id === action.supplier_id);
          const color = ACTION_COLOR[action.action] ?? 'muted';
          return (
            <div key={action.action_id} className="flex flex-wrap items-center justify-between gap-2 text-sm">
              <div className="flex min-w-0 items-center gap-2">
                <span
                  className={`shrink-0 rounded-pill border px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-wider ${PILL_CLASSES[color]}`}
                >
                  {ACTION_TEXT[action.action] ?? action.action}
                </span>
                <span className="truncate text-text-primary">{supplier?.name ?? action.supplier_id}</span>
                <span className="hidden truncate text-xs text-text-muted sm:inline">
                  {REASON_TEXT[action.primary_reason_code] ?? action.primary_reason_code}
                </span>
              </div>
              <span className="shrink-0 font-mono text-xs tabular-nums text-text-secondary">
                {inr(action.amount)}
              </span>
            </div>
          );
        })}
      </div>
    </motion.div>
  );
}

export function HistoryPage() {
  // `state` (and the sim controls) come from the shared provider mounted in App.tsx — no
  // separate GET /state here, so this page opens instantly off whatever the Live tab already
  // loaded instead of re-fetching and flashing empty every visit.
  const {
    state,
    agentStatus,
    simRunning,
    controlsBusy,
    handleStep,
    handlePlayPause,
    handleReset,
  } = useSimData();
  const [decisions, setDecisions] = useState<DecisionObject[] | null>(null);

  useEffect(() => {
    getDecisionHistory().then(setDecisions);
  }, []);

  const sorted = decisions ? [...decisions].sort((a, b) => b.sim_day - a.sim_day) : null;

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

      <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-6">
        <div>
          <h1 className="text-xl font-semibold text-text-primary">Decision history</h1>
          <p className="text-sm text-text-secondary">
            Every decision the agent has made this run, most recent first.
          </p>
        </div>

        {!sorted ? (
          <EmptyState text="Loading decision history…" />
        ) : sorted.length === 0 ? (
          <EmptyState text="No decisions recorded yet." />
        ) : (
          <motion.div
            variants={staggerContainer}
            initial="hidden"
            animate="visible"
            className="flex flex-col gap-4"
          >
            {sorted.map((decision) => (
              <DecisionCard key={decision.decision_id} decision={decision} state={state} />
            ))}
          </motion.div>
        )}
      </main>
    </div>
  );
}
