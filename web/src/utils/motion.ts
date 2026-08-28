import type { Transition, Variants } from 'framer-motion';

// HELM.md §8 caps *reactive* transitions (chaos re-optimize, decision flips) at
// 300ms so the demo never feels laggy under rapid clicking. The one-time page
// reveal isn't that kind of transition — it runs once on mount — so it's free
// to be a little more generous and springy without breaking that rule's intent.
export const SPRING: Transition = { type: 'spring', stiffness: 520, damping: 32, mass: 0.6 };
export const SPRING_SOFT: Transition = { type: 'spring', stiffness: 300, damping: 26, mass: 0.7 };

// Use for anything that updates in response to a live event (chaos panel,
// decision diffs) — stays inside the 300ms budget.
export const QUICK: Transition = { duration: 0.22, ease: [0.16, 1, 0.3, 1] };

export const EASE_OUT = [0.16, 1, 0.3, 1] as const;

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14, scale: 0.97 },
  visible: { opacity: 1, y: 0, scale: 1, transition: SPRING_SOFT },
};

export const staggerContainer: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.04 } },
};

export const hoverLift = {
  y: -3,
  scale: 1.012,
  boxShadow: '0 12px 28px -10px rgba(45, 212, 167, 0.25)',
  transition: SPRING,
};
export const tapPress = { scale: 0.97, transition: { duration: 0.1 } };

export const glowPulse: Variants = {
  animate: {
    opacity: [0.5, 1, 0.5],
    scale: [1, 1.15, 1],
    transition: { duration: 2.2, repeat: Infinity, ease: 'easeInOut' },
  },
};
