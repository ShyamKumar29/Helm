import { motion } from 'framer-motion';
import { useMemo } from 'react';

interface BlurTextProps {
  text: string;
  delay?: number;
  animateBy?: 'words' | 'letters';
  direction?: 'top' | 'bottom';
  className?: string;
  onAnimationComplete?: () => void;
}

// Reimplemented from a usage example only, no source was provided. Splits
// text into words or letters and reveals each with a blur+translate stagger.
export function BlurText({
  text,
  delay = 150,
  animateBy = 'words',
  direction = 'top',
  className = '',
  onAnimationComplete,
}: BlurTextProps) {
  const units = useMemo(
    () => (animateBy === 'letters' ? text.split('') : text.split(' ')),
    [text, animateBy],
  );

  const offset = direction === 'top' ? -16 : 16;

  return (
    <span className={className}>
      {units.map((unit, i) => (
        <motion.span
          key={`${unit}-${i}`}
          initial={{ opacity: 0, y: offset, filter: 'blur(10px)' }}
          animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
          transition={{
            duration: 0.5,
            delay: (i * delay) / 1000,
            ease: [0.16, 1, 0.3, 1],
          }}
          onAnimationComplete={i === units.length - 1 ? onAnimationComplete : undefined}
          style={{ display: 'inline-block', whiteSpace: animateBy === 'letters' ? 'pre' : 'normal' }}
        >
          {unit}
          {animateBy === 'words' && i < units.length - 1 ? ' ' : ''}
        </motion.span>
      ))}
    </span>
  );
}

export default BlurText;
