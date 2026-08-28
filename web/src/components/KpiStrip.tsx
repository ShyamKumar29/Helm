import { motion } from 'framer-motion';
import { Activity, AlertTriangle, Landmark, Scale, ShieldCheck, TrendingUp, Wallet } from 'lucide-react';
import type { ReactNode } from 'react';
import { Area, AreaChart, ResponsiveContainer } from 'recharts';
import type { ComparisonMetrics, Forecast, State } from '../types';
import { inr } from '../utils/format';
import { fadeUp, hoverLift, staggerContainer } from '../utils/motion';
import { AnimatedNumber } from './AnimatedNumber';
import { EmptyState } from './EmptyState';

interface KpiStripProps {
  state: State | null;
  forecast: Forecast | null;
  comparison: ComparisonMetrics | null;
}

function healthBand(score: number): 'good' | 'warn' | 'bad' {
  if (score >= 80) return 'good';
  if (score >= 50) return 'warn';
  return 'bad';
}

const BAND_TEXT: Record<string, string> = {
  good: 'text-accent',
  warn: 'text-warning',
  bad: 'text-danger',
};

const BAND_HEX: Record<string, string> = {
  good: '#2FE0B8',
  warn: '#F0A93E',
  bad: '#FF5C5C',
};

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (data.length < 2) return null;
  const points = data.map((v, i) => ({ i, v }));
  const gradientId = `spark-${color.replace('#', '')}`;
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 h-8 opacity-70">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={points} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.35} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area
            dataKey="v"
            stroke={color}
            strokeWidth={1.4}
            fill={`url(#${gradientId})`}
            isAnimationActive
            animationDuration={900}
            animationEasing="ease-out"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// The icon badge doubles as a progress ring when a gauge value is given —
// used for Health, the one KPI that's a score out of 100 rather than a figure.
function IconBadge({ icon, gaugeValue, gaugeColor }: { icon: ReactNode; gaugeValue?: number; gaugeColor?: string }) {
  if (gaugeValue == null || !gaugeColor) {
    return (
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent-dim/50 text-accent">
        {icon}
      </span>
    );
  }
  const r = 12;
  const c = 2 * Math.PI * r;
  const offset = c - (Math.max(0, Math.min(100, gaugeValue)) / 100) * c;
  return (
    <span className="relative flex h-7 w-7 shrink-0 items-center justify-center">
      <svg width="28" height="28" viewBox="0 0 28 28" className="-rotate-90">
        <circle cx="14" cy="14" r={r} stroke="currentColor" strokeOpacity={0.15} strokeWidth={2.5} fill="none" className="text-border" />
        <motion.circle
          cx="14"
          cy="14"
          r={r}
          stroke={gaugeColor}
          strokeWidth={2.5}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          initial={{ strokeDashoffset: c }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center" style={{ color: gaugeColor }}>
        {icon}
      </span>
    </span>
  );
}

interface TileProps {
  label: string;
  icon: ReactNode;
  value: ReactNode;
  valueClassName?: string;
  sublabel?: string;
  sparkline?: number[];
  sparklineColor?: string;
  gaugeValue?: number;
  gaugeColor?: string;
  featured?: boolean;
}

function KpiTile({
  label,
  icon,
  value,
  valueClassName = '',
  sublabel,
  sparkline,
  sparklineColor,
  gaugeValue,
  gaugeColor,
  featured = false,
}: TileProps) {
  return (
    <motion.div
      variants={fadeUp}
      whileHover={hoverLift}
      className={`relative flex min-w-0 flex-col gap-3 overflow-hidden rounded-card border bg-panel px-4 py-3.5 ${
        featured ? 'flex-[1.3] min-w-[180px] border-accent-dim' : 'flex-1 min-w-[140px] border-border'
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <span className="label-caps whitespace-nowrap">{label}</span>
        <motion.span
          whileHover={{ scale: 1.12, rotate: 6 }}
          transition={{ type: 'spring', stiffness: 400, damping: 18 }}
        >
          <IconBadge icon={icon} gaugeValue={gaugeValue} gaugeColor={gaugeColor} />
        </motion.span>
      </div>
      <div className="relative z-10 flex flex-col gap-0.5">
        <span
          className={`truncate font-mono font-semibold tabular-nums text-text-primary ${featured ? 'text-2xl' : 'text-xl'} ${valueClassName}`}
        >
          {value}
        </span>
        {sublabel && <span className="text-xs text-text-secondary">{sublabel}</span>}
      </div>
      {sparkline && sparklineColor && <Sparkline data={sparkline} color={sparklineColor} />}
    </motion.div>
  );
}

export function KpiStrip({ state, forecast, comparison }: KpiStripProps) {
  if (!state || !forecast) {
    return (
      <div className="rounded-card border border-border bg-panel">
        <EmptyState text="Waiting on state and forecast to compute KPIs…" />
      </div>
    );
  }

  const health = comparison?.agent.health_score ?? null;
  const band = health !== null ? healthBand(health) : 'warn';
  const savingsPerDay = comparison?.agent.savings_per_day ?? null;
  const costDelta = comparison?.delta.net_working_capital_cost ?? null;
  const shortfallDays = comparison?.agent.shortfall_days ?? 0;

  const trend = forecast.buckets.slice(0, 14).map((b) => b.p50);

  return (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="flex flex-wrap gap-3"
    >
      <KpiTile
        featured
        label="Health"
        icon={<Activity size={13} strokeWidth={2.2} />}
        value={
          health !== null ? (
            <AnimatedNumber value={health} format={(v) => `${Math.round(v)}/100`} />
          ) : (
            '—'
          )
        }
        valueClassName={BAND_TEXT[band]}
        gaugeValue={health ?? 0}
        gaugeColor={BAND_HEX[band]}
        sublabel="agent policy score"
      />
      <KpiTile
        featured
        label="Deployable"
        icon={<Wallet size={14} strokeWidth={2} />}
        value={<AnimatedNumber value={forecast.deployable_cash} format={inr} />}
        valueClassName="text-accent"
        sublabel="safe to spend today"
        sparkline={trend}
        sparklineColor="#2FE0B8"
      />
      <KpiTile
        label="Buffer Required"
        icon={<ShieldCheck size={14} strokeWidth={2} />}
        value={<AnimatedNumber value={forecast.buffer_required} format={inr} />}
        sublabel={`through ${forecast.binding_date}`}
      />
      <KpiTile
        label="Cash Available"
        icon={<Landmark size={14} strokeWidth={2} />}
        value={<AnimatedNumber value={state.cash_available} format={inr} />}
        sparkline={trend.slice().reverse()}
        sparklineColor="#4FB3D9"
      />
      <KpiTile
        label="Shortfall"
        icon={<AlertTriangle size={14} strokeWidth={2} />}
        value={
          <AnimatedNumber
            value={shortfallDays}
            format={(v) => `${Math.round(v)} day${Math.round(v) === 1 ? '' : 's'}`}
          />
        }
        valueClassName={shortfallDays > 0 ? 'text-danger' : 'text-accent'}
      />
      <KpiTile
        label="Savings / day"
        icon={<TrendingUp size={14} strokeWidth={2} />}
        value={
          savingsPerDay !== null ? <AnimatedNumber value={savingsPerDay} format={inr} /> : '—'
        }
        valueClassName={savingsPerDay !== null && savingsPerDay < 0 ? 'text-danger' : 'text-accent'}
      />
      <KpiTile
        label="Cost Δ"
        icon={<Scale size={14} strokeWidth={2} />}
        value={costDelta !== null ? <AnimatedNumber value={costDelta} format={inr} /> : '—'}
        valueClassName={costDelta !== null && costDelta < 0 ? 'text-accent' : 'text-danger'}
        sublabel="vs baseline · lower is better"
      />
    </motion.div>
  );
}
