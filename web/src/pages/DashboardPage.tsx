import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { useEffect, useState } from 'react';
import {
  getComparison,
  getComparisonCalm,
  getDecision,
  getDecisionCalm,
  getEvents,
  getExplanation,
  getForecast,
  getForecastCalm,
  getState,
} from '../api/client';
import { ActivityTimeline } from '../components/ActivityTimeline';
import { AmbientBackground } from '../components/AmbientBackground';
import { CashFanChart } from '../components/CashFanChart';
import { ChaosPanel, type ChaosPreset } from '../components/ChaosPanel';
import { DecisionQueue } from '../components/DecisionQueue';
import { ExplanationPanel } from '../components/ExplanationPanel';
import { Header } from '../components/Header';
import { KpiStrip } from '../components/KpiStrip';
import { Scoreboard } from '../components/Scoreboard';
import { WeightSliders } from '../components/WeightSliders';
import type {
  AgentStatus,
  ComparisonMetrics,
  DecisionObject,
  Explanation,
  Forecast,
  HelmEvent,
  State,
} from '../types';
import { fadeUp, staggerContainer } from '../utils/motion';

function Panel({
  title,
  className = '',
  children,
}: {
  title: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <motion.div
      variants={fadeUp}
      className={`flex flex-col rounded-card border border-border bg-panel ${className}`}
    >
      <div className="border-b border-border px-4 py-3">
        <span className="label-caps">{title}</span>
      </div>
      <div className="flex-1 overflow-hidden p-4">{children}</div>
    </motion.div>
  );
}

let syntheticEventCounter = 0;

export function DashboardPage() {
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

  useEffect(() => {
    getState().then(setState);
    getForecastCalm().then(setForecast);
    getComparisonCalm().then(setComparison);
    getDecisionCalm().then(setDecision);
    getEvents().then(setEvents);
  }, []);

  const handleExplain = () => {
    if (!decision) return;
    setExplanationOpen(true);
    if (!explanation || explanation.decision_id !== decision.decision_id) {
      getExplanation(decision.decision_id).then(setExplanation);
    }
  };

  const handleChaosFire = (preset: ChaosPreset) => {
    if (agentStatus === 'RE-OPTIMIZING') return;

    setAgentStatus('RE-OPTIMIZING');

    window.setTimeout(async () => {
      // Steps 3 + 6 of HELM.md §5: the fan chart redraws and KPIs settle on
      // post-shock values — not just a card pulse and a log line.
      const [shockedForecast, shockedComparison, shockedDecision] = await Promise.all([
        getForecast(),
        getComparison(),
        getDecision(),
      ]);

      const flippedIds = new Set(
        shockedDecision.diff_from_previous.flipped.map((f) => f.target_id),
      );

      setForecast(shockedForecast);
      setComparison(shockedComparison);
      setDecision(shockedDecision);
      setFlippedTargetIds(flippedIds);
      setHasShocked(true);

      syntheticEventCounter += 1;
      const newEvent: HelmEvent = {
        event_id: `EVT-DEMO-${syntheticEventCounter}`,
        sim_day: shockedDecision.sim_day,
        date: shockedDecision.run_at,
        type: preset.eventType,
        source: 'JUDGE_INJECTED',
        payload: { target: preset.target, raw: preset.payload },
        materiality_score: 0.42,
        triggered_reoptimization: true,
        triggered_decision_id: shockedDecision.decision_id,
      };
      setEvents((prev) => [...(prev ?? []), newEvent]);
      setAgentStatus('RUNNING');

      window.setTimeout(() => setFlippedTargetIds(new Set()), 3000);
    }, 1100);
  };

  return (
    <div className="relative flex min-h-screen flex-col bg-page">
      <AmbientBackground />
      <Header status={agentStatus} simDay={state?.sim_day ?? 0} asOf={state?.as_of ?? ''} />

      <motion.main
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="flex flex-1 flex-col gap-4 p-6"
      >
        <motion.div
          animate={{
            opacity: agentStatus === 'RE-OPTIMIZING' ? 0.45 : 1,
            filter: agentStatus === 'RE-OPTIMIZING' ? 'grayscale(0.6)' : 'grayscale(0)',
          }}
          transition={{ duration: 0.2 }}
        >
          <KpiStrip state={state} forecast={forecast} comparison={comparison} />
        </motion.div>

        <div className="grid flex-1 grid-cols-1 gap-4 xl:grid-cols-[60%_40%]">
          <div className="flex flex-col gap-4">
            <CashFanChart forecast={forecast} />
            <Panel title="Scoreboard — Agent vs Baseline" className="h-auto">
              <Scoreboard comparison={comparison} />
            </Panel>
          </div>
          <div className="flex flex-col gap-4">
            <Panel title="Decision Queue" className="h-96">
              <DecisionQueue
                decision={decision}
                state={state}
                flippedTargetIds={flippedTargetIds}
                onExplain={handleExplain}
              />
            </Panel>
            <Panel title="Activity Timeline" className="h-64">
              <ActivityTimeline events={events} />
            </Panel>
          </div>
        </div>

        <Panel title="Chaos Panel · Weight Sliders" className="h-auto">
          <div className="flex flex-col gap-5">
            <ChaosPanel
              disabled={agentStatus === 'RE-OPTIMIZING' || hasShocked}
              onFire={handleChaosFire}
            />
            <div className="border-t border-border pt-4">
              <WeightSliders initial={decision?.objective_weights ?? null} />
            </div>
          </div>
        </Panel>
      </motion.main>

      <ExplanationPanel
        explanation={explanation}
        open={explanationOpen}
        onClose={() => setExplanationOpen(false)}
      />
    </div>
  );
}
