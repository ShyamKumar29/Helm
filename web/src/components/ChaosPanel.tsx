import { motion } from 'framer-motion';
import { Banknote, CloudLightning, ReceiptText, TrendingDown } from 'lucide-react';
import { hoverLift, tapPress } from '../utils/motion';

export interface ChaosPreset {
  id: string;
  label: string;
  eventType: string;
  target: string;
  payload: string;
  icon: typeof Banknote;
}

export const CHAOS_PRESETS: ChaosPreset[] = [
  {
    id: 'ashwin-late',
    label: 'Ashwin Motors pays 3 weeks late',
    eventType: 'RECEIVABLE_DELAYED',
    target: 'RCV-0004',
    payload: 'delay_days: 21',
    icon: TrendingDown,
  },
  {
    id: 'rate-jump',
    label: 'Bank rate jumps to 18%',
    eventType: 'RATE_CHANGE',
    target: 'FAC-001',
    payload: 'new_apr_pct: 18.0',
    icon: Banknote,
  },
  {
    id: 'gst-notice',
    label: 'Emergency GST notice ₹9L in 5 days',
    eventType: 'NEW_OBLIGATION',
    target: '—',
    payload: 'amount: 900000, category: TAX',
    icon: ReceiptText,
  },
  {
    id: 'supplier-distress',
    label: 'Meenakshi Steels in distress',
    eventType: 'SUPPLIER_DISTRESS',
    target: 'SUP-001',
    payload: 'new_liquidity_stress: 0.85',
    icon: CloudLightning,
  },
];

interface ChaosPanelProps {
  disabled: boolean;
  onFire: (preset: ChaosPreset) => void;
}

export function ChaosPanel({ disabled, onFire }: ChaosPanelProps) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-text-secondary">
        Inject a live shock and watch the agent re-optimize. No live engine wired up yet — this
        replays the recorded shock in <span className="font-mono text-text-muted">decision.json</span> so the
        sequence can be demoed end to end.
      </p>
      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
        {CHAOS_PRESETS.map((preset) => {
          const Icon = preset.icon;
          return (
            <motion.button
              key={preset.id}
              type="button"
              disabled={disabled}
              onClick={() => onFire(preset)}
              whileHover={disabled ? undefined : hoverLift}
              whileTap={disabled ? undefined : tapPress}
              className="flex flex-col gap-2 rounded-lg border border-border bg-panel/60 px-3.5 py-3 text-left disabled:cursor-not-allowed disabled:opacity-40"
            >
              <span className="flex h-7 w-7 items-center justify-center rounded-full bg-warning/10 text-warning">
                <Icon size={14} strokeWidth={2} />
              </span>
              <span className="text-sm leading-snug text-text-primary">{preset.label}</span>
              <span className="font-mono text-[10.5px] tabular-nums text-text-muted">
                {preset.eventType} · {preset.target}
              </span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
