import { motion } from 'framer-motion';
import { useMemo, useState } from 'react';
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
import type { Forecast } from '../types';
import { inr, simDate } from '../utils/format';
import { fadeUp } from '../utils/motion';
import { AnimatedNumber } from './AnimatedNumber';
import { EmptyState } from './EmptyState';
import { CompassRose } from './icons/CompassRose';

interface CashFanChartProps {
  forecast: Forecast | null;
}

interface TooltipPayloadItem {
  payload: { date: string; p10: number; p50: number; p90: number };
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: TooltipPayloadItem[] }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg border border-border bg-panel px-3 py-2 text-xs font-mono tabular-nums shadow-lg">
      <div className="mb-1 text-text-secondary">{simDate(point.date)}</div>
      <div className="text-accent">P50 {inr(point.p50)}</div>
      <div className="text-text-muted">
        P10 {inr(point.p10)} · P90 {inr(point.p90)}
      </div>
    </div>
  );
}

const RANGES = [
  { label: '30D', days: 30 },
  { label: '60D', days: 60 },
  { label: '90D', days: 90 },
] as const;

export function CashFanChart({ forecast }: CashFanChartProps) {
  const [rangeDays, setRangeDays] = useState<number>(90);

  const data = useMemo(() => {
    if (!forecast) return [];
    return forecast.buckets
      .filter((b) => b.day_offset <= rangeDays)
      .map((b) => ({ date: b.date, p10: b.p10, band: b.p90 - b.p10, p50: b.p50, p90: b.p90 }));
  }, [forecast, rangeDays]);

  if (!forecast || forecast.buckets.length === 0) {
    return (
      <div className="rounded-card border border-border bg-hero">
        <EmptyState text="Forecast unavailable — waiting for the next simulation tick…" />
      </div>
    );
  }

  const tickInterval = Math.max(1, Math.floor(data.length / 8));

  return (
    <motion.div
      variants={fadeUp}
      initial="hidden"
      animate="visible"
      className="relative flex flex-col gap-4 overflow-hidden rounded-card border border-border bg-hero p-5"
    >
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -left-24 -top-24 h-80 w-80 rounded-full bg-accent/10 blur-3xl"
        animate={{ x: [0, 50, -10, 0], y: [0, 30, 10, 0] }}
        transition={{ duration: 16, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute -right-16 bottom-0 h-64 w-64 rounded-full bg-accent/5 blur-3xl"
        animate={{ x: [0, -30, 0], y: [0, -20, 0] }}
        transition={{ duration: 20, repeat: Infinity, ease: 'easeInOut' }}
      />
      <CompassRose className="pointer-events-none absolute -bottom-16 -right-16 h-72 w-72 text-accent/[0.07]" />

      <div className="relative flex items-start justify-between gap-4">
        <div>
          <span className="label-caps inline-flex items-center gap-1.5">
            <motion.span
              className="h-1.5 w-1.5 rounded-full bg-accent"
              animate={{ opacity: [1, 0.35, 1], scale: [1, 1.3, 1] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
            />
            Deployable Cash
          </span>
          <div className="font-mono text-4xl font-semibold tabular-nums text-text-primary">
            <AnimatedNumber value={forecast.deployable_cash} format={inr} />
          </div>
          <p className="voice-narrative mt-1.5 max-w-md text-[15px] leading-snug text-text-secondary">
            {forecast.binding_reason}
          </p>
        </div>

        <div className="flex flex-col items-end gap-2">
          <div className="flex items-center gap-1 rounded-pill border border-border bg-panel/60 p-1">
            {RANGES.map((r) => {
              const active = rangeDays === r.days;
              return (
                <button
                  key={r.label}
                  type="button"
                  onClick={() => setRangeDays(r.days)}
                  className="relative rounded-pill px-2.5 py-1 font-mono text-[11px] tabular-nums text-text-secondary transition-colors duration-150"
                >
                  {active && (
                    <motion.span
                      layoutId="range-pill"
                      transition={{ type: 'spring', stiffness: 500, damping: 34 }}
                      className="absolute inset-0 rounded-pill bg-accent"
                    />
                  )}
                  <span className={`relative z-10 ${active ? 'text-page font-semibold' : ''}`}>
                    {r.label}
                  </span>
                </button>
              );
            })}
          </div>
          <div className="flex flex-col items-end gap-1 text-right">
            <span className="label-caps">Buffer Required</span>
            <span className="font-mono text-lg tabular-nums text-text-primary">
              <AnimatedNumber value={forecast.buffer_required} format={inr} />
            </span>
            <span className="text-xs text-warning">binds {simDate(forecast.binding_date)}</span>
          </div>
        </div>
      </div>

      <div className="relative h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#2FE0B8" stopOpacity={0.26} />
                <stop offset="100%" stopColor="#2FE0B8" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tickFormatter={simDate}
              interval={tickInterval}
              tick={{ fill: '#56635F', fontSize: 11, fontFamily: 'Geist Mono, monospace' }}
              axisLine={{ stroke: '#1C242B' }}
              tickLine={false}
            />
            <YAxis
              tickFormatter={(v: number) => inr(v)}
              tick={{ fill: '#56635F', fontSize: 11, fontFamily: 'Geist Mono, monospace' }}
              axisLine={false}
              tickLine={false}
              width={70}
            />
            <Tooltip content={<ChartTooltip />} />
            <ReferenceLine y={0} stroke="#FF5C5C" strokeDasharray="4 4" strokeWidth={1.5} />
            <ReferenceLine
              x={forecast.binding_date}
              stroke="#F0A93E"
              strokeDasharray="3 3"
              label={{ value: 'binding', position: 'insideTopRight', fill: '#F0A93E', fontSize: 10 }}
            />
            <Area
              dataKey="p10"
              stackId="band"
              stroke="none"
              fill="transparent"
              isAnimationActive
              animationDuration={700}
              animationEasing="ease-out"
            />
            <Area
              dataKey="band"
              stackId="band"
              stroke="none"
              fill="url(#bandFill)"
              isAnimationActive
              animationDuration={700}
              animationEasing="ease-out"
            />
            <Line
              dataKey="p50"
              stroke="#2FE0B8"
              strokeWidth={2}
              dot={false}
              isAnimationActive
              animationDuration={700}
              animationEasing="ease-out"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </motion.div>
  );
}
