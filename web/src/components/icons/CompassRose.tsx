interface CompassRoseProps {
  className?: string;
}

// Decorative watermark for the forecast panel — bearing rings and tick marks,
// like the compass rose printed on a nautical chart under the plotted course.
// Purely atmospheric: low-opacity, non-interactive, never carries information.
export function CompassRose({ className }: CompassRoseProps) {
  const ticks = Array.from({ length: 24 }, (_, i) => i * 15);

  return (
    <svg viewBox="0 0 200 200" className={className} aria-hidden="true">
      <circle cx="100" cy="100" r="90" stroke="currentColor" strokeWidth="0.75" fill="none" />
      <circle cx="100" cy="100" r="64" stroke="currentColor" strokeWidth="0.75" fill="none" />
      <circle cx="100" cy="100" r="38" stroke="currentColor" strokeWidth="0.75" fill="none" />
      {ticks.map((deg) => {
        const major = deg % 90 === 0;
        const outer = 90;
        const inner = major ? 76 : 84;
        const rad = (deg * Math.PI) / 180;
        return (
          <line
            key={deg}
            x1={100 + inner * Math.cos(rad)}
            y1={100 + inner * Math.sin(rad)}
            x2={100 + outer * Math.cos(rad)}
            y2={100 + outer * Math.sin(rad)}
            stroke="currentColor"
            strokeWidth={major ? 1 : 0.6}
          />
        );
      })}
    </svg>
  );
}
