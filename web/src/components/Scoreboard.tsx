import { motion } from 'framer-motion';
import type { ComparisonMetrics } from '../types';
import { inr } from '../utils/format';
import { fadeUp } from '../utils/motion';
import { AnimatedNumber } from './AnimatedNumber';
import { EmptyState } from './EmptyState';

interface ScoreboardProps {
  comparison: ComparisonMetrics | null;
}

interface RowDef {
  label: string;
  agent: number;
  baseline: number;
  format: (v: number) => string;
  lowerIsBetter: boolean;
}

function Row({ label, agent, baseline, format, lowerIsBetter }: RowDef) {
  const agentBetter = lowerIsBetter ? agent <= baseline : agent >= baseline;
  return (
    <div className="grid grid-cols-[1fr_auto_auto] items-center gap-4 border-b border-border/60 py-2.5 last:border-b-0">
      <span className="text-sm text-text-secondary">{label}</span>
      <span
        className={`w-28 text-right font-mono text-sm font-semibold tabular-nums ${
          agentBetter ? 'text-accent' : 'text-text-primary'
        }`}
      >
        <AnimatedNumber value={agent} format={format} />
      </span>
      <span
        className={`w-28 text-right font-mono text-sm tabular-nums ${
          !agentBetter ? 'text-danger' : 'text-text-muted'
        }`}
      >
        <AnimatedNumber value={baseline} format={format} />
      </span>
    </div>
  );
}

export function Scoreboard({ comparison }: ScoreboardProps) {
  if (!comparison) {
    return <EmptyState text="Waiting on comparison metrics…" />;
  }

  const { agent, baseline, delta } = comparison;
  const days = (v: number) => `${Math.round(v)} day${Math.round(v) === 1 ? '' : 's'}`;

  const rows: RowDef[] = [
    { label: 'Discounts captured', agent: agent.discounts_captured, baseline: baseline.discounts_captured, format: inr, lowerIsBetter: false },
    { label: 'Financing cost', agent: agent.financing_cost, baseline: baseline.financing_cost, format: inr, lowerIsBetter: true },
    { label: 'Penalties paid', agent: agent.penalties_paid, baseline: baseline.penalties_paid, format: inr, lowerIsBetter: true },
    { label: 'Shortfall days', agent: agent.shortfall_days, baseline: baseline.shortfall_days, format: days, lowerIsBetter: true },
    { label: 'Obligations missed', agent: agent.obligations_missed, baseline: baseline.obligations_missed, format: (v) => `${Math.round(v)}`, lowerIsBetter: true },
    { label: 'Avg. supplier stress', agent: agent.avg_supplier_stress, baseline: baseline.avg_supplier_stress, format: (v) => v.toFixed(2), lowerIsBetter: true },
  ];

  return (
    <motion.div variants={fadeUp} className="flex h-full flex-col gap-3">
      <div className="flex items-start justify-between gap-4 rounded-lg border border-accent-dim bg-accent-dim/20 px-4 py-3">
        <div>
          <span className="label-caps">Net Working Capital Cost — Δ</span>
          <div className={`font-mono text-2xl font-semibold tabular-nums ${delta.net_working_capital_cost < 0 ? 'text-accent' : 'text-danger'}`}>
            <AnimatedNumber value={delta.net_working_capital_cost} format={inr} />
          </div>
        </div>
        <p className="voice-narrative max-w-[14rem] text-right text-sm text-text-secondary">
          the agent's cost versus a static-rules baseline, over the same {comparison.sim_day} days
        </p>
      </div>

      <div className="grid grid-cols-[1fr_auto_auto] gap-4 px-1 text-right">
        <span />
        <span className="label-caps w-28 text-accent">Agent</span>
        <span className="label-caps w-28 text-text-muted">Baseline</span>
      </div>
      <div className="px-1">
        {rows.map((r) => (
          <Row key={r.label} {...r} />
        ))}
      </div>
    </motion.div>
  );
}
