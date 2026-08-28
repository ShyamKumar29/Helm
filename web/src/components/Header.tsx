import { AnimatePresence, motion } from 'framer-motion';
import { Bell, ChevronDown, Pause, Play, RotateCcw, SkipForward } from 'lucide-react';
import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import type { AgentStatus } from '../types';
import { simDate } from '../utils/format';
import { hoverLift, SPRING, tapPress } from '../utils/motion';
import { HelmWheel } from './icons/HelmWheel';

interface HeaderProps {
  status: AgentStatus;
  simDay: number;
  asOf: string;
  // Sim controls (POST /sim/step, /sim/play, /sim/pause, /sim/reset — FINAL.md §10). All
  // optional: History/About render a bare Header with no live sim to control, so the buttons
  // there stay inert rather than requiring three callers to wire dead handlers.
  onStep?: () => void;
  onPlayPause?: () => void;
  onReset?: () => void;
  simRunning?: boolean;
  controlsBusy?: boolean;
}

function StatusPill({ status }: { status: AgentStatus }) {
  const running = status === 'RUNNING';
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.span
        key={status}
        initial={{ opacity: 0, y: -4 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 4 }}
        transition={SPRING}
        className={`inline-flex items-center gap-1.5 rounded-pill border px-3 py-1 text-xs font-medium font-mono tabular-nums ${
          running
            ? 'border-accent-dim bg-accent-dim text-accent'
            : 'border-warning/30 bg-warning/10 text-warning'
        }`}
      >
        {running ? (
          <motion.span
            className="h-1.5 w-1.5 rounded-full bg-accent"
            animate={{ opacity: [1, 0.4, 1] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
          />
        ) : (
          <motion.span
            className="flex"
            animate={{ rotate: 360 }}
            transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
          >
            <HelmWheel size={11} strokeWidth={2.2} />
          </motion.span>
        )}
        {running ? 'RUNNING' : 'RE-OPTIMIZING'}
      </motion.span>
    </AnimatePresence>
  );
}

const NAV_TABS = [
  { to: '/dashboard', label: 'Live', end: true },
  { to: '/dashboard/replay', label: 'Replay', end: false },
  { to: '/dashboard/history', label: 'History', end: false },
  { to: '/dashboard/about', label: 'About', end: false },
];

function NavTabs() {
  return (
    <nav className="flex items-center gap-1 rounded-pill border border-border bg-panel/60 p-1">
      {NAV_TABS.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          end={tab.end}
          className={({ isActive }) =>
            `rounded-pill px-3 py-1 font-mono text-xs transition-colors duration-150 ${
              isActive
                ? 'bg-accent font-semibold text-page'
                : 'text-text-secondary hover:text-text-primary'
            }`
          }
        >
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}

function IconButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick?: () => void;
  disabled?: boolean;
  children: ReactNode;
}) {
  return (
    <motion.button
      type="button"
      aria-label={label}
      onClick={onClick}
      disabled={disabled}
      whileHover={disabled ? undefined : hoverLift}
      whileTap={disabled ? undefined : tapPress}
      className="flex h-8 w-8 items-center justify-center rounded-full border border-border text-text-secondary transition-colors duration-150 hover:border-accent-dim hover:bg-accent-dim/40 hover:text-accent disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-border disabled:hover:bg-transparent disabled:hover:text-text-secondary"
    >
      {children}
    </motion.button>
  );
}

export function Header({
  status,
  simDay,
  asOf,
  onStep,
  onPlayPause,
  onReset,
  simRunning = false,
  controlsBusy = false,
}: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-border bg-panel/80 px-6 py-3 backdrop-blur">
      <div className="flex items-center gap-4">
        <motion.span
          whileHover={{ rotate: 25 }}
          transition={{ type: 'spring', stiffness: 300, damping: 18 }}
          className="flex h-8 w-8 items-center justify-center rounded-full border border-accent-dim text-accent"
        >
          <HelmWheel size={17} />
        </motion.span>
        <span className="font-mono text-base font-semibold uppercase tracking-[0.2em] text-text-primary">
          Helm
        </span>
        <StatusPill status={status} />
        <span className="font-mono text-sm tabular-nums text-text-secondary">
          Day {simDay} · {asOf ? simDate(asOf) : '—'}
        </span>
        <NavTabs />
      </div>

      <div className="flex items-center gap-2">
        <IconButton
          label="Step forward one day"
          onClick={onStep}
          disabled={!onStep || controlsBusy || simRunning}
        >
          <SkipForward size={14} strokeWidth={2} />
        </IconButton>
        <IconButton
          label={simRunning ? 'Pause' : 'Play'}
          onClick={onPlayPause}
          disabled={!onPlayPause || controlsBusy}
        >
          {simRunning ? (
            <Pause size={13} strokeWidth={2} fill="currentColor" />
          ) : (
            <Play size={13} strokeWidth={2} fill="currentColor" />
          )}
        </IconButton>
        <IconButton
          label="Reset simulation"
          onClick={onReset}
          disabled={!onReset || controlsBusy}
        >
          <RotateCcw size={13} strokeWidth={2} />
        </IconButton>

        <div className="mx-2 h-6 w-px bg-border" />

        <motion.button
          type="button"
          whileHover={hoverLift}
          whileTap={tapPress}
          className="flex items-center gap-2 rounded-pill border border-border bg-panel px-1.5 py-1 pr-3 text-sm text-text-primary transition-colors duration-150 hover:border-accent-dim"
        >
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-gradient-to-br from-accent to-accent-dim text-xs font-semibold text-page">
            S
          </span>
          Simulation
          <ChevronDown size={12} strokeWidth={2} className="text-text-muted" />
        </motion.button>

        <motion.button
          type="button"
          aria-label="Notifications"
          whileHover={hoverLift}
          whileTap={tapPress}
          className="relative flex h-8 w-8 items-center justify-center rounded-full border border-border text-text-secondary transition-colors duration-150 hover:border-accent-dim hover:bg-accent-dim/40 hover:text-accent"
        >
          <Bell size={14} strokeWidth={2} />
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-warning" />
        </motion.button>
      </div>
    </header>
  );
}
