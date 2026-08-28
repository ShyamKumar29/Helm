import { motion } from 'framer-motion';
import { ArrowRight, Compass, ShieldCheck, TrendingUp } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { BlurText } from '../components/landing/BlurText';
import { CountUp } from '../components/landing/CountUp';
import PixelSwap from '../components/landing/PixelSwap';
import RotatingEarth from '../components/landing/RotatingEarth';
import SpecularButton from '../components/landing/SpecularButton';
import { HelmWheel } from '../components/icons/HelmWheel';
import { CompassRose } from '../components/icons/CompassRose';
import { EASE_OUT } from '../utils/motion';

const fadeUpOnView = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE_OUT } },
};

function StaticRulesCard() {
  return (
    <div className="flex h-full w-full flex-col justify-between gap-4 rounded-card border border-border bg-panel px-6 py-6">
      <span className="label-caps text-text-muted">The old way</span>
      <p className="voice-narrative text-lg text-text-secondary">
        "Always pay in 30 days. Always take the discount. Never draw the bank line."
      </p>
      <p className="text-sm text-text-muted">
        Static rules, written once, that never see a late payment coming.
      </p>
    </div>
  );
}

function AgentDecisionCard() {
  return (
    <div className="flex h-full w-full flex-col justify-between gap-4 rounded-card border border-accent-dim bg-hero px-6 py-6">
      <span className="label-caps inline-flex items-center gap-1.5 text-accent">
        <HelmWheel size={12} strokeWidth={2.2} />
        HELM decides
      </span>
      <p className="voice-narrative text-lg text-text-primary">
        "Draw ₹8,33,000 on the bank line at 13.5% to capture the 2% discount — the trade nets
        ₹11,700."
      </p>
      <p className="text-sm text-text-secondary">
        Grounded in the forecast, weighed against every alternative, explained in plain English.
      </p>
    </div>
  );
}

function StatBlock({
  from,
  to,
  suffix,
  prefix,
  label,
  separator,
}: {
  from: number;
  to: number;
  suffix?: string;
  prefix?: string;
  label: string;
  separator?: string;
}) {
  return (
    <motion.div variants={fadeUpOnView} className="flex flex-col gap-1">
      <div className="font-mono text-4xl font-semibold tabular-nums text-accent sm:text-5xl">
        <CountUp from={from} to={to} duration={1.4} prefix={prefix} suffix={suffix} separator={separator} />
      </div>
      <span className="label-caps">{label}</span>
    </motion.div>
  );
}

export function LandingPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-screen flex-col bg-page">
      {/* Hero */}
      <section className="relative flex min-h-screen flex-col overflow-hidden px-6 py-6 sm:px-10">
        <CompassRose className="pointer-events-none absolute -right-40 -top-40 h-[36rem] w-[36rem] text-accent/[0.05]" />

        <div className="relative z-10 flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full border border-accent-dim text-accent">
            <HelmWheel size={19} />
          </span>
          <span className="font-mono text-lg font-semibold uppercase tracking-[0.25em] text-text-primary">
            Helm
          </span>
        </div>

        <div className="relative z-10 flex flex-1 flex-col items-center justify-center gap-10 py-16 text-center lg:flex-row lg:gap-16 lg:text-left">
          <motion.div
            initial="hidden"
            animate="visible"
            variants={{ visible: { transition: { staggerChildren: 0.08 } } }}
            className="flex max-w-xl flex-col items-center gap-6 lg:items-start"
          >
            <motion.span variants={fadeUpOnView} className="label-caps text-accent">
              Autonomous working-capital agent
            </motion.span>
            <h1 className="text-4xl font-semibold leading-[1.1] text-text-primary sm:text-5xl">
              <BlurText
                text="We replaced the treasurer who guesses."
                delay={90}
                animateBy="words"
                direction="top"
              />
            </h1>
            <motion.p
              variants={fadeUpOnView}
              className="voice-narrative text-lg leading-relaxed text-text-secondary"
            >
              A company's treasurer decides every morning where limited cash goes. He does it
              with static rules, and those rules break the moment a customer pays late. HELM
              forecasts the uncertainty, decides what to do about it, and explains why — in
              plain English, every time.
            </motion.p>
            <motion.div variants={fadeUpOnView}>
              <SpecularButton
                size="lg"
                radius={18}
                tint="#ffffff"
                tintOpacity={0}
                blur={0}
                textColor="#f5f5f5"
                lineColor="#2FE0B8"
                baseColor="#242b31"
                intensity={1}
                shineSize={45}
                shineFade={45}
                thickness={1}
                speed={0.15}
                followMouse
                proximity={260}
                autoAnimate
                onClick={() => navigate('/dashboard')}
              >
                <span className="inline-flex items-center gap-2">
                  Enter the dashboard
                  <ArrowRight size={16} strokeWidth={2.2} />
                </span>
              </SpecularButton>
            </motion.div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.8, ease: EASE_OUT, delay: 0.2 }}
            className="w-full max-w-md lg:max-w-lg"
          >
            <RotatingEarth width={560} height={560} />
          </motion.div>
        </div>
      </section>

      {/* Stats */}
      <motion.section
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: '-15%' }}
        variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
        className="border-t border-border px-6 py-20 sm:px-10"
      >
        <div className="mx-auto grid max-w-5xl grid-cols-2 gap-10 sm:grid-cols-4">
          <StatBlock from={0} to={90} suffix="-day" label="Monte Carlo forecast horizon" />
          <StatBlock from={0} to={5316} prefix="₹" separator="," label="Savings per day vs. baseline" />
          <StatBlock from={0} to={82} suffix="/100" label="Agent health score" />
          <StatBlock from={0} to={0} suffix=" days" label="Shortfall days under the agent" />
        </div>
      </motion.section>

      {/* Before / after */}
      <motion.section
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: '-15%' }}
        variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
        className="border-t border-border px-6 py-20 sm:px-10"
      >
        <div className="mx-auto flex max-w-3xl flex-col items-center gap-6 text-center">
          <motion.span variants={fadeUpOnView} className="label-caps text-accent">
            Same invoice, two treasurers
          </motion.span>
          <motion.h2 variants={fadeUpOnView} className="text-3xl font-semibold text-text-primary">
            Click to see who's actually deciding
          </motion.h2>
          <motion.div variants={fadeUpOnView} className="w-full max-w-md">
            <PixelSwap
              firstContent={<StaticRulesCard />}
              secondContent={<AgentDecisionCard />}
              pixelSize={28}
              gap={0}
              pixelRadius={0}
              pixelSpin={0}
              pixelScale={0.35}
              duration={700}
              pixelDuration={320}
              pattern="random"
              randomness={0.3}
              fade
              trigger="click"
              pixelColor="#0A0D10"
              className="block w-full"
            />
          </motion.div>
          <motion.span variants={fadeUpOnView} className="text-xs text-text-muted">
            click the card
          </motion.span>
        </div>
      </motion.section>

      {/* Feature strip */}
      <motion.section
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: '-15%' }}
        variants={{ visible: { transition: { staggerChildren: 0.1 } } }}
        className="border-t border-border px-6 py-20 sm:px-10"
      >
        <div className="mx-auto grid max-w-5xl gap-6 sm:grid-cols-3">
          {[
            {
              icon: Compass,
              title: 'Forecasts the uncertainty',
              body: 'A 90-day Monte Carlo band, not a single guess — deployable_cash is what you can safely spend today.',
            },
            {
              icon: ShieldCheck,
              title: 'Shows the roads not taken',
              body: 'Every decision ships with its rejected alternatives and the exact numeric reason each one lost.',
            },
            {
              icon: TrendingUp,
              title: 'Proves it, continuously',
              body: 'Benchmarked live against a static-rules baseline, so the value is measured, never asserted.',
            },
          ].map(({ icon: Icon, title, body }) => (
            <motion.div
              key={title}
              variants={fadeUpOnView}
              className="flex flex-col gap-3 rounded-card border border-border bg-panel px-6 py-6"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-accent-dim/50 text-accent">
                <Icon size={16} strokeWidth={2} />
              </span>
              <h3 className="text-base font-semibold text-text-primary">{title}</h3>
              <p className="text-sm leading-relaxed text-text-secondary">{body}</p>
            </motion.div>
          ))}
        </div>
      </motion.section>

      {/* Closing CTA */}
      <motion.section
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, margin: '-15%' }}
        variants={fadeUpOnView}
        className="flex flex-col items-center gap-6 border-t border-border px-6 py-24 text-center sm:px-10"
      >
        <h2 className="max-w-xl text-3xl font-semibold text-text-primary">
          Sit down. Poke at it. Break it with the chaos panel.
        </h2>
        <SpecularButton
          size="lg"
          radius={18}
          tint="#ffffff"
          tintOpacity={0}
          textColor="#f5f5f5"
          lineColor="#2FE0B8"
          baseColor="#242b31"
          intensity={1}
          shineSize={45}
          shineFade={45}
          thickness={1}
          speed={0.15}
          followMouse
          proximity={260}
          autoAnimate
          onClick={() => navigate('/dashboard')}
        >
          <span className="inline-flex items-center gap-2">
            Enter the dashboard
            <ArrowRight size={16} strokeWidth={2.2} />
          </span>
        </SpecularButton>
      </motion.section>
    </div>
  );
}
