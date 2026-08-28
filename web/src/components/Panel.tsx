import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { fadeUp } from '../utils/motion';

interface PanelProps {
  title: string;
  className?: string;
  children: ReactNode;
  // Optional right-aligned slot in the header row — a count badge, a filter, etc.
  action?: ReactNode;
}

// Shared card chrome for every bordered panel on the dashboard (Decision Queue, Activity
// Timeline, Scoreboard, Replay's Events/Decisions columns, ...) — one definition so they all
// stay visually identical instead of drifting as each page re-implements its own border/label.
export function Panel({ title, className = '', children, action }: PanelProps) {
  return (
    <motion.div
      variants={fadeUp}
      className={`flex flex-col rounded-card border border-border bg-panel ${className}`}
    >
      <div className="flex items-center justify-between gap-2 border-b border-border px-4 py-3">
        <span className="label-caps">{title}</span>
        {action}
      </div>
      <div className="flex-1 overflow-hidden p-4">{children}</div>
    </motion.div>
  );
}
