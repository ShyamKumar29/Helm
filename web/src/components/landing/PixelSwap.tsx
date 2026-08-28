import { motion } from 'framer-motion';
import type { ReactNode } from 'react';
import { useEffect, useMemo, useRef, useState } from 'react';

interface PixelSwapProps {
  firstContent: ReactNode;
  secondContent: ReactNode;
  pixelSize?: number;
  gap?: number;
  pixelRadius?: number;
  pixelSpin?: number;
  pixelScale?: number;
  duration?: number;
  pixelDuration?: number;
  pattern?: 'random' | 'sequential' | 'radial';
  randomness?: number;
  fade?: boolean;
  trigger?: 'click' | 'hover';
  pixelColor?: string;
  className?: string;
}

interface Tile {
  key: string;
  x: number;
  y: number;
  delay: number;
}

// Reimplemented from a usage example only, no source was provided. Mechanic:
// a grid of tiles pops in to fully cover the content, the content swaps while
// hidden underneath, then the tiles pop back out to reveal it.
export function PixelSwap({
  firstContent,
  secondContent,
  pixelSize = 48,
  gap = 0,
  pixelRadius = 0,
  pixelSpin = 0,
  pixelScale = 0.35,
  duration = 900,
  pixelDuration = 350,
  pattern = 'random',
  randomness = 0,
  fade = true,
  trigger = 'click',
  pixelColor = '#0A0D10',
  className = '',
}: PixelSwapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [showFirst, setShowFirst] = useState(true);
  const [covering, setCovering] = useState(false);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width, height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const tiles = useMemo<Tile[]>(() => {
    if (!size.width || !size.height) return [];
    const step = pixelSize + gap;
    const cols = Math.ceil(size.width / step);
    const rows = Math.ceil(size.height / step);
    const cells: { x: number; y: number; order: number }[] = [];

    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        cells.push({ x: col * step, y: row * step, order: 0 });
      }
    }

    const total = cells.length;
    if (pattern === 'random') {
      const order = [...Array(total).keys()];
      for (let i = order.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [order[i], order[j]] = [order[j], order[i]];
      }
      cells.forEach((c, i) => (c.order = order[i]));
    } else if (pattern === 'radial') {
      const cx = size.width / 2;
      const cy = size.height / 2;
      const dists = cells.map((c) => Math.hypot(c.x - cx, c.y - cy));
      const maxDist = Math.max(...dists, 1);
      cells.forEach((c, i) => (c.order = Math.round((dists[i] / maxDist) * total)));
    } else {
      cells.forEach((c, i) => (c.order = i));
    }

    return cells.map((c, i) => {
      const base = total > 1 ? (c.order / (total - 1)) * duration : 0;
      const jitter = randomness ? (Math.random() - 0.5) * randomness * duration : 0;
      return { key: `${i}`, x: c.x, y: c.y, delay: Math.max(0, base + jitter) };
    });
  }, [size, pixelSize, gap, pattern, randomness, duration]);

  const runSwap = () => {
    if (covering) return;
    setCovering(true);
    const totalCoverTime = duration + pixelDuration;
    window.setTimeout(() => setShowFirst((v) => !v), totalCoverTime * 0.55);
    window.setTimeout(() => setCovering(false), totalCoverTime + 40);
  };

  const interactionProps =
    trigger === 'hover'
      ? { onMouseEnter: runSwap }
      : { onClick: runSwap };

  return (
    <div
      ref={containerRef}
      {...interactionProps}
      className={`relative inline-block cursor-pointer select-none overflow-hidden ${className}`}
    >
      <div className="relative">{showFirst ? firstContent : secondContent}</div>

      <div className="pointer-events-none absolute inset-0">
        {tiles.map((tile) => (
          <motion.span
            key={tile.key}
            initial={false}
            animate={
              covering
                ? { scale: 1, opacity: 1, rotate: 0 }
                : { scale: pixelScale, opacity: 0, rotate: pixelSpin }
            }
            transition={{
              duration: pixelDuration / 1000,
              delay: tile.delay / 1000,
              ease: [0.16, 1, 0.3, 1],
              opacity: fade ? undefined : { duration: 0 },
            }}
            style={{
              position: 'absolute',
              left: tile.x,
              top: tile.y,
              width: pixelSize,
              height: pixelSize,
              borderRadius: pixelRadius,
              background: pixelColor,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default PixelSwap;
