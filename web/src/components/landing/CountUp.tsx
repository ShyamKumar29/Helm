import { animate, motion, useInView, useMotionValue, useTransform } from 'framer-motion';
import { useEffect, useRef } from 'react';

interface CountUpProps {
  from: number;
  to: number;
  separator?: string;
  direction?: 'up' | 'down';
  duration?: number;
  className?: string;
  decimals?: number;
  prefix?: string;
  suffix?: string;
}

// Reimplemented from a usage example only (no source was available) — animates
// on scroll into view rather than on mount, which is the useful behavior for a
// landing-page stat rather than a dashboard figure (see AnimatedNumber for that).
export function CountUp({
  from,
  to,
  separator = '',
  direction = 'up',
  duration = 1,
  className,
  decimals = 0,
  prefix = '',
  suffix = '',
}: CountUpProps) {
  const startValue = direction === 'down' ? to : from;
  const endValue = direction === 'down' ? from : to;

  const motionValue = useMotionValue(startValue);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: '-10% 0px' });

  const display = useTransform(motionValue, (latest) => {
    const rounded = latest.toFixed(decimals);
    const [intPart, decPart] = rounded.split('.');
    const withSeparator = separator
      ? intPart.replace(/\B(?=(\d{3})+(?!\d))/g, separator)
      : intPart;
    return `${prefix}${withSeparator}${decPart ? `.${decPart}` : ''}${suffix}`;
  });

  useEffect(() => {
    if (!inView) return;
    const controls = animate(motionValue, endValue, {
      duration,
      ease: [0.16, 1, 0.3, 1],
    });
    return controls.stop;
  }, [inView, endValue, duration, motionValue]);

  return (
    <motion.span ref={ref} className={className}>
      {display}
    </motion.span>
  );
}

export default CountUp;
