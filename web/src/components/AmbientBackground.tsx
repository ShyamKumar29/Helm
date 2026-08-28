import { motion } from 'framer-motion';

// A restrained, React-Bits-style "Aurora" wash for the dashboard's page
// background — slow-drifting blurred glow, not a WebGL scene, so it never
// competes with the data. One accent colour only, per HELM.md's own rule.
export function AmbientBackground() {
  return (
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <motion.div
        className="absolute -left-1/4 -top-1/3 h-[60rem] w-[60rem] rounded-full bg-accent/[0.07] blur-[140px]"
        animate={{ x: [0, 120, -40, 0], y: [0, 80, 40, 0] }}
        transition={{ duration: 42, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute -right-1/4 top-1/4 h-[50rem] w-[50rem] rounded-full bg-info/[0.05] blur-[140px]"
        animate={{ x: [0, -90, 30, 0], y: [0, 60, -30, 0] }}
        transition={{ duration: 55, repeat: Infinity, ease: 'easeInOut' }}
      />
      <motion.div
        className="absolute bottom-[-20%] left-1/3 h-[45rem] w-[45rem] rounded-full bg-accent/[0.05] blur-[160px]"
        animate={{ x: [0, 60, -60, 0], y: [0, -50, 20, 0] }}
        transition={{ duration: 48, repeat: Infinity, ease: 'easeInOut' }}
      />
    </div>
  );
}
