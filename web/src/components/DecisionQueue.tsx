import { AnimatePresence, motion } from 'framer-motion';
import { ChevronDown, MessageCircleQuestion } from 'lucide-react';
import { useState } from 'react';
import type { Action, DecisionObject, State } from '../types';
import { inr, simDate } from '../utils/format';
import { ACTION_COLOR, ACTION_TEXT, REASON_TEXT } from '../utils/reason';
import { EmptyState } from './EmptyState';

interface DecisionQueueProps {
  decision: DecisionObject | null;
  state: State | null;
  flippedTargetIds: Set<string>;
  onExplain: () => void;
}

const PILL_CLASSES: Record<string, string> = {
  accent: 'bg-accent-dim text-accent border-accent-dim',
  info: 'bg-info/10 text-info border-info/30',
  warning: 'bg-warning/10 text-warning border-warning/30',
  purple: 'bg-purple/10 text-purple border-purple/30',
  muted: 'bg-border/40 text-text-muted border-border',
};

function WhyNotPanel({ action }: { action: Action }) {
  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: 'auto', opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
      className="overflow-hidden"
    >
      <div className="mt-3 rounded-lg border border-l-2 border-warning/40 border-l-warning bg-panel/60 px-3 py-2.5">
        <span className="label-caps text-warning">Rejected alternatives</span>
        <div className="mt-2 flex flex-col gap-2">
          {action.rejected_alternatives.map((alt) => (
            <div key={alt.action} className="flex items-center justify-between gap-3 text-xs">
              <span className="text-text-secondary">{ACTION_TEXT[alt.action] ?? alt.action}</span>
              <span className="font-mono tabular-nums text-danger">{inr(alt.delta)}</span>
              <span className="hidden max-w-[45%] truncate text-text-muted sm:block">
                {REASON_TEXT[alt.reason_code] ?? alt.reason_code}
              </span>
            </div>
          ))}
        </div>
      </div>
    </motion.div>
  );
}

function ActionCard({
  action,
  state,
  flipped,
  onExplain,
}: {
  action: Action;
  state: State | null;
  flipped: boolean;
  onExplain: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const supplier = state?.suppliers.find((s) => s.id === action.supplier_id);
  const invoice = state?.invoices.find((i) => i.id === action.target_id);
  const color = ACTION_COLOR[action.action] ?? 'muted';

  return (
    <motion.div
      layout
      animate={
        flipped
          ? { borderColor: ['#F0A93E', '#F0A93E', '#1C242B'] }
          : {}
      }
      transition={{ duration: 2.6, times: [0, 0.3, 1] }}
      className="rounded-lg border border-border bg-panel/60 px-3.5 py-3"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <span className="truncate text-sm font-medium text-text-primary">
            {supplier?.name ?? action.supplier_id}
          </span>
          <span className="font-mono text-[11px] tabular-nums text-text-muted">
            {action.target_id}
            {invoice && ` · due ${simDate(invoice.due_date)}`}
          </span>
        </div>
        <span className="font-mono text-sm font-semibold tabular-nums text-text-primary">
          {inr(action.amount)}
        </span>
      </div>

      <div className="mt-2.5 flex items-center justify-between gap-2">
        <span
          className={`rounded-pill border px-2 py-0.5 font-mono text-[10.5px] font-semibold uppercase tracking-wider ${PILL_CLASSES[color]}`}
        >
          {ACTION_TEXT[action.action] ?? action.action}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={onExplain}
            className="flex items-center gap-1 rounded-pill px-2 py-1 text-[11px] text-text-secondary transition-colors duration-150 hover:bg-accent-dim/40 hover:text-accent"
          >
            <MessageCircleQuestion size={12} strokeWidth={2} />
            Why?
          </button>
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            aria-expanded={expanded}
            className="flex items-center gap-1 rounded-pill px-2 py-1 text-[11px] text-text-secondary transition-colors duration-150 hover:bg-accent-dim/40 hover:text-accent"
          >
            <motion.span animate={{ rotate: expanded ? 180 : 0 }} transition={{ duration: 0.15 }} className="flex">
              <ChevronDown size={12} strokeWidth={2} />
            </motion.span>
            {expanded ? 'Hide' : 'Details'}
          </button>
        </div>
      </div>

      <p className="mt-2 text-xs text-text-secondary">
        {REASON_TEXT[action.primary_reason_code] ?? action.primary_reason_code}
        {action.funding_source !== 'NONE' && ` · via ${action.funding_source.replace('_', ' ').toLowerCase()}`}
      </p>

      <AnimatePresence initial={false}>{expanded && <WhyNotPanel action={action} />}</AnimatePresence>
    </motion.div>
  );
}

export function DecisionQueue({ decision, state, flippedTargetIds, onExplain }: DecisionQueueProps) {
  if (!decision) {
    return <EmptyState text="Waiting on the latest decision…" />;
  }
  if (decision.actions.length === 0) {
    return <EmptyState text="No open invoices — nothing to decide today." />;
  }

  return (
    <div className="no-scrollbar flex h-full flex-col gap-2.5 overflow-y-auto px-1">
      {decision.actions.map((action) => (
        <ActionCard
          key={action.action_id}
          action={action}
          state={state}
          flipped={flippedTargetIds.has(action.target_id)}
          onExplain={onExplain}
        />
      ))}
    </div>
  );
}
