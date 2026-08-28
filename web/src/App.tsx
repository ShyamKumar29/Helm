import { motion } from 'framer-motion';
import { useEffect, useState } from 'react';
import { getComparison, getForecast, getState } from './api/client';
import { CashFanChart } from './components/CashFanChart';
import { EmptyState } from './components/EmptyState';
import { Header } from './components/Header';
import { KpiStrip } from './components/KpiStrip';
import type { ComparisonMetrics, Forecast, State } from './types';
import { fadeUp, staggerContainer } from './utils/motion';

function Placeholder({ title, height }: { title: string; height: string }) {
  return (
    <motion.div
      variants={fadeUp}
      className={`flex flex-col rounded-card border border-dashed border-border bg-panel/60 ${height}`}
    >
      <div className="border-b border-border/60 px-4 py-3">
        <span className="label-caps">{title}</span>
      </div>
      <div className="flex flex-1 items-center justify-center">
        <motion.div
          animate={{ opacity: [0.5, 0.9, 0.5] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: 'easeInOut' }}
        >
          <EmptyState text="Coming next" />
        </motion.div>
      </div>
    </motion.div>
  );
}

function App() {
  const [state, setState] = useState<State | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [comparison, setComparison] = useState<ComparisonMetrics | null>(null);

  useEffect(() => {
    getState().then(setState);
    getForecast().then(setForecast);
    getComparison().then(setComparison);
  }, []);

  return (
    <div className="flex min-h-screen flex-col bg-page">
      <Header status="RUNNING" simDay={state?.sim_day ?? 0} asOf={state?.as_of ?? ''} />

      <motion.main
        variants={staggerContainer}
        initial="hidden"
        animate="visible"
        className="flex flex-1 flex-col gap-4 p-6"
      >
        <KpiStrip state={state} forecast={forecast} comparison={comparison} />

        <div className="grid flex-1 grid-cols-1 gap-4 xl:grid-cols-[60%_40%]">
          <div className="flex flex-col gap-4">
            <CashFanChart forecast={forecast} />
            <Placeholder title="Scoreboard — Agent vs Baseline" height="h-64" />
          </div>
          <div className="flex flex-col gap-4">
            <Placeholder title="Decision Queue" height="h-96" />
            <Placeholder title="Activity Timeline" height="h-64" />
          </div>
        </div>

        <Placeholder title="Chaos Panel · Weight Sliders" height="h-40" />
      </motion.main>
    </div>
  );
}

export default App;
