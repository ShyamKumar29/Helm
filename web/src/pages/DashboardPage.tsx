import { motion } from 'framer-motion';
import { USE_MOCK } from '../api/client';
import { ActivityTimeline } from '../components/ActivityTimeline';
import { AmbientBackground } from '../components/AmbientBackground';
import { CashFanChart } from '../components/CashFanChart';
import { ChaosPanel } from '../components/ChaosPanel';
import { DecisionQueue } from '../components/DecisionQueue';
import { ExplanationPanel } from '../components/ExplanationPanel';
import { Header } from '../components/Header';
import { KpiStrip } from '../components/KpiStrip';
import { Panel } from '../components/Panel';
import { Scoreboard } from '../components/Scoreboard';
import { WeightSliders } from '../components/WeightSliders';
import { useSimData } from '../state/SimDataProvider';
import { staggerContainer } from '../utils/motion';

// All the live data, the WS connection and every control handler live in <SimDataProvider>,
// mounted once in App.tsx above the router — this page is a pure consumer. That's what keeps
// the dashboard's numbers in place when you leave for /dashboard/history and come back,
// instead of tearing the socket down and refetching everything from zero on every tab switch.
export function DashboardPage() {
  const {
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
    closeExplanation,
    handleExplain,
    handleStep,
    handlePlayPause,
    handleReset,
    handleWeightsCommit,
    handleChaosFire,
  } = useSimData();

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
              <WeightSliders
                initial={decision?.objective_weights ?? null}
                onCommit={USE_MOCK ? undefined : handleWeightsCommit}
              />
            </div>
          </div>
        </Panel>
      </motion.main>

      <ExplanationPanel explanation={explanation} open={explanationOpen} onClose={closeExplanation} />
    </div>
  );
}
