import { AnimatePresence, motion } from 'framer-motion';
import type { HelmEvent } from '../types';
import { simDate } from '../utils/format';
import { EVENT_TEXT } from '../utils/reason';
import { EmptyState } from './EmptyState';

interface ActivityTimelineProps {
  events: HelmEvent[] | null;
}

function EntryRow({ event }: { event: HelmEvent }) {
  const acted = event.triggered_reoptimization;
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', stiffness: 400, damping: 32 }}
      className={`flex items-start gap-3 border-b border-border/50 py-2.5 last:border-b-0 ${
        acted ? '' : 'opacity-55'
      }`}
    >
      <span
        className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${acted ? 'bg-accent' : 'bg-text-muted'}`}
      />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-sm text-text-primary">
            {EVENT_TEXT[event.type] ?? event.type}
          </span>
          <span className="shrink-0 font-mono text-[11px] tabular-nums text-text-muted">
            {simDate(event.date)}
          </span>
        </div>
        <span className="font-mono text-[11px] tabular-nums text-text-muted">
          {event.materiality_score !== null
            ? `materiality ${event.materiality_score.toFixed(2)}`
            : 'materiality n/a'}
          {acted ? ' · re-optimized' : ' · below threshold, held course'}
        </span>
      </div>
    </motion.div>
  );
}

export function ActivityTimeline({ events }: ActivityTimelineProps) {
  if (!events) {
    return <EmptyState text="Waiting on the event log…" />;
  }
  if (events.length === 0) {
    return <EmptyState text="No events yet this run." />;
  }

  const sorted = [...events].sort((a, b) => b.sim_day - a.sim_day);

  return (
    <div className="no-scrollbar flex h-full flex-col overflow-y-auto px-1">
      <AnimatePresence initial={false}>
        {sorted.map((event) => (
          <EntryRow key={event.event_id} event={event} />
        ))}
      </AnimatePresence>
    </div>
  );
} 
