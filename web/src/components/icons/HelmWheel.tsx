interface HelmWheelProps {
  size?: number;
  strokeWidth?: number;
  className?: string;
}

// The product's namesake: a ship's wheel. Doubles as the agent's status motif —
// it turns when the agent is correcting course (RE-OPTIMIZING) and sits still,
// hand on the helm, when holding steady (RUNNING).
export function HelmWheel({ size = 16, strokeWidth = 1.9, className }: HelmWheelProps) {
  // Kept to 3 diameters (6 spokes), no handle pegs — this renders as small as
  // 11px in the status pill, where more detail just blurs into a flower blob.
  const diameters = [0, 60, 120];

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="7.5" stroke="currentColor" strokeWidth={strokeWidth} />
      <circle cx="12" cy="12" r="2.3" stroke="currentColor" strokeWidth={strokeWidth} />
      {diameters.map((deg) => (
        <line
          key={deg}
          x1={12 - 7.5 * Math.cos((deg * Math.PI) / 180)}
          y1={12 - 7.5 * Math.sin((deg * Math.PI) / 180)}
          x2={12 + 7.5 * Math.cos((deg * Math.PI) / 180)}
          y2={12 + 7.5 * Math.sin((deg * Math.PI) / 180)}
          stroke="currentColor"
          strokeWidth={strokeWidth}
        />
      ))}
    </svg>
  );
}
