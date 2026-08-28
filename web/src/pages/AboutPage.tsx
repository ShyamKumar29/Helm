import { motion } from 'framer-motion';
import { Compass, ShieldCheck, TrendingUp } from 'lucide-react';
import { USE_MOCK } from '../api/client';
import { AmbientBackground } from '../components/AmbientBackground';
import { Header } from '../components/Header';
import { HelmWheel } from '../components/icons/HelmWheel';
import { useSimData } from '../state/SimDataProvider';
import { fadeUp, staggerContainer } from '../utils/motion';

const STAGES = [
  {
    icon: Compass,
    title: '1. Forecast',
    body: 'Monte Carlo simulation over receivable delays, financing costs, and obligations produces a P10/P50/P90 uncertainty band for the next 90 days — not a single point estimate. deployable_cash is the amount of today\'s cash that stays safe across that whole band.',
  },
  {
    icon: ShieldCheck,
    title: '2. Decide',
    body: 'A constrained optimization (MILP over scenarios, hard 2-second timeout with a greedy fallback) assigns every open invoice an explicit action — pay, delay, finance, or hold — each with its rejected alternatives and a numeric reason.',
  },
  {
    icon: TrendingUp,
    title: '3. Explain',
    body: 'A language model narrates the decision that already exists. It never computes a number — every figure in the explanation is grounded in the DecisionObject\'s own fields, including an explicit "would change if…" for every call.',
  },
];

const RULES = [
  'The engine is a pure function of State — no database, no env vars, no network, no stdout.',
  'The engine emits reason_code enums, never prose. English is generated only in the explainer.',
  'Deterministic output — the same (sim_day, decision_id) seed produces the same decision every time.',
  'A solve never hangs — hard 2-second timeout, then a greedy fallback.',
  'Every open invoice gets an entry in actions[] — a HOLD is explicit, never inferred from absence.',
];

export function AboutPage() {
  const { state, agentStatus, simRunning, controlsBusy, handleStep, handlePlayPause, handleReset } =
    useSimData();

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
        className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-12 p-6 py-12"
      >
        <motion.div variants={fadeUp} className="flex flex-col gap-4 text-center">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full border border-accent-dim text-accent">
            <HelmWheel size={24} />
          </span>
          <h1 className="text-2xl font-semibold text-text-primary">How HELM decides</h1>
          <p className="voice-narrative mx-auto max-w-xl text-lg text-text-secondary">
            "A company's treasurer decides every morning where limited cash goes. He does it
            with static rules, and those rules break the moment a customer pays late. We
            replaced him."
          </p>
        </motion.div>

        <motion.div variants={fadeUp} className="flex flex-col gap-4">
          <span className="label-caps text-accent">The pipeline</span>
          <div className="grid gap-4 sm:grid-cols-3">
            {STAGES.map(({ icon: Icon, title, body }) => (
              <div
                key={title}
                className="flex flex-col gap-3 rounded-card border border-border bg-panel px-5 py-5"
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-full bg-accent-dim/50 text-accent">
                  <Icon size={15} strokeWidth={2} />
                </span>
                <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
                <p className="text-sm leading-relaxed text-text-secondary">{body}</p>
              </div>
            ))}
          </div>
        </motion.div>

        <motion.div variants={fadeUp} className="flex flex-col gap-4">
          <span className="label-caps text-accent">Non-negotiable rules</span>
          <div className="rounded-card border border-border bg-panel px-5 py-4">
            <ul className="flex flex-col gap-3">
              {RULES.map((rule) => (
                <li key={rule} className="flex gap-2.5 text-sm text-text-secondary">
                  <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-accent" />
                  {rule}
                </li>
              ))}
            </ul>
          </div>
        </motion.div>

        <motion.div variants={fadeUp} className="rounded-card border border-accent-dim bg-hero px-5 py-5 text-center">
          <p className="voice-narrative text-base text-text-primary">
            The single most important number on screen is{' '}
            <span className="font-mono font-semibold text-accent">deployable_cash</span> — it's
            what makes this a decision system, not a dashboard.
          </p>
        </motion.div>
      </motion.main>
    </div>
  );
}
