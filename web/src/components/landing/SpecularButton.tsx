import { animate, motion, useMotionValue, useTransform } from 'framer-motion';
import type { CSSProperties, MouseEvent, ReactNode } from 'react';
import { useEffect, useRef } from 'react';

interface SpecularButtonProps {
  children: ReactNode;
  size?: 'sm' | 'md' | 'lg';
  radius?: number;
  tint?: string;
  tintOpacity?: number;
  blur?: number;
  textColor?: string;
  lineColor?: string;
  baseColor?: string;
  intensity?: number;
  shineSize?: number;
  shineFade?: number;
  thickness?: number;
  speed?: number;
  followMouse?: boolean;
  proximity?: number;
  autoAnimate?: boolean;
  onClick?: () => void;
  className?: string;
}

const SIZE_PADDING: Record<'sm' | 'md' | 'lg', string> = {
  sm: '0.5rem 1.1rem',
  md: '0.7rem 1.6rem',
  lg: '0.95rem 2.1rem',
};

const SIZE_FONT: Record<'sm' | 'md' | 'lg', string> = {
  sm: '0.8125rem',
  md: '0.9375rem',
  lg: '1.0625rem',
};

// Reimplemented from a usage example only, no source was provided. Behavior:
// a gradient "shine" travels along the button's border, following the cursor
// when it comes within `proximity` px, and idly orbiting the border on a loop
// when `autoAnimate` is set and no cursor is near.
export function SpecularButton({
  children,
  size = 'md',
  radius = 14,
  tint = '#ffffff',
  tintOpacity = 0,
  blur = 0,
  textColor = '#f5f5f5',
  lineColor = '#2FE0B8',
  baseColor = '#333a40',
  intensity = 1,
  shineSize = 40,
  shineFade = 40,
  thickness = 1,
  speed = 0.35,
  followMouse = true,
  proximity = 200,
  autoAnimate = true,
  onClick,
  className = '',
}: SpecularButtonProps) {
  const wrapperRef = useRef<HTMLButtonElement>(null);
  const mx = useMotionValue(50);
  const my = useMotionValue(50);
  const opacity = useMotionValue(autoAnimate ? intensity * 0.6 : 0);
  const loopAngle = useRef(0);
  const rafRef = useRef<number | null>(null);

  const shineBackground = useTransform([mx, my], ([x, y]: number[]) =>
    `radial-gradient(${shineSize}% ${shineSize}% at ${x}% ${y}%, ${lineColor}, transparent ${shineFade}%)`,
  );

  useEffect(() => {
    if (!autoAnimate) return;
    // Radians/second — tuned so the default speed (~0.35) drifts a full lap in
    // well over half a minute; this is ambient texture, not a spinning wheel.
    const angularVelocity = Math.max(speed, 0.02) * 0.6;
    let raf: number;
    let last = performance.now();
    const step = (now: number) => {
      const dt = (now - last) / 1000;
      last = now;
      loopAngle.current += angularVelocity * dt;
      const rad = loopAngle.current;
      mx.set(50 + 50 * Math.cos(rad));
      my.set(50 + 50 * Math.sin(rad));
      raf = requestAnimationFrame(step);
      rafRef.current = raf;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [autoAnimate, speed, mx, my]);

  const handlePointerMove = (e: MouseEvent<HTMLButtonElement>) => {
    if (!followMouse || !wrapperRef.current) return;
    const rect = wrapperRef.current.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dist = Math.hypot(e.clientX - cx, e.clientY - cy);

    if (dist <= proximity) {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      const px = ((e.clientX - rect.left) / rect.width) * 100;
      const py = ((e.clientY - rect.top) / rect.height) * 100;
      mx.set(Math.max(-20, Math.min(120, px)));
      my.set(Math.max(-20, Math.min(120, py)));
      animate(opacity, intensity, { duration: 0.2 });
    } else if (!autoAnimate) {
      animate(opacity, 0, { duration: 0.3 });
    }
  };

  const handlePointerLeave = () => {
    if (!autoAnimate) {
      animate(opacity, 0, { duration: 0.3 });
    } else {
      animate(opacity, intensity * 0.6, { duration: 0.3 });
    }
  };

  const innerStyle: CSSProperties = {
    borderRadius: Math.max(radius - thickness, 0),
    padding: SIZE_PADDING[size],
    fontSize: SIZE_FONT[size],
    color: textColor,
    background: `linear-gradient(180deg, ${tint}${tintOpacityToHex(tintOpacity)}, ${tint}${tintOpacityToHex(tintOpacity)}), #14181c`,
  };

  return (
    <motion.button
      ref={wrapperRef}
      type="button"
      onClick={onClick}
      onMouseMove={handlePointerMove}
      onMouseLeave={handlePointerLeave}
      whileHover={{ scale: 1.015 }}
      whileTap={{ scale: 0.98 }}
      transition={{ type: 'spring', stiffness: 400, damping: 26 }}
      className={`group relative inline-flex ${className}`}
      style={{
        borderRadius: radius,
        padding: thickness,
        background: baseColor,
      }}
    >
      <motion.span
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          borderRadius: radius,
          filter: blur ? `blur(${blur}px)` : undefined,
          opacity,
          background: shineBackground,
        }}
      />
      <span className="relative z-10 font-medium leading-none" style={innerStyle}>
        {children}
      </span>
    </motion.button>
  );
}

function tintOpacityToHex(opacity: number): string {
  const clamped = Math.max(0, Math.min(1, opacity));
  return Math.round(clamped * 255)
    .toString(16)
    .padStart(2, '0');
}

export default SpecularButton;
