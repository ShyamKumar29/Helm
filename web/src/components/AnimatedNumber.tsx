import { animate, motion, useMotionValue, useTransform } from 'framer-motion';
import { useEffect, useRef } from 'react';

interface AnimatedNumberProps {
  value: number;
  format: (value: number) => string;
  className?: string;
}

// Counts up from 0 on first mount (the page-reveal moment), then re-tweens
// quickly between values afterward (e.g. a chaos event changing a KPI) —
// the latter stays inside HELM.md's 300ms budget for reactive updates.
export function AnimatedNumber({ value, format, className }: AnimatedNumberProps) {
  const motionValue = useMotionValue(0);
  const display = useTransform(motionValue, (latest) => format(latest));
  const hasMounted = useRef(false);

  useEffect(() => {
    const controls = animate(motionValue, value, {
      duration: hasMounted.current ? 0.25 : 0.7,
      ease: [0.16, 1, 0.3, 1],
    });
    hasMounted.current = true;
    return controls.stop;
  }, [value, motionValue]);

  return (
    <motion.span className={className}>{display}</motion.span>
  );
}
