import { useState } from 'react';
import type { ObjectiveWeights } from '../types';

interface WeightSlidersProps {
  initial: ObjectiveWeights | null;
  onCommit?: (weights: ObjectiveWeights) => void;
}

const LABELS: Record<keyof ObjectiveWeights, string> = {
  discount: 'Discount capture',
  financing_cost: 'Financing cost',
  penalty: 'Penalty avoidance',
  liquidity_risk: 'Liquidity risk',
  supplier_stress: 'Supplier stress',
};

const DEFAULT_WEIGHTS: ObjectiveWeights = {
  discount: 1,
  financing_cost: 1,
  penalty: 1,
  liquidity_risk: 1.5,
  supplier_stress: 0.8,
};

export function WeightSliders({ initial, onCommit }: WeightSlidersProps) {
  const [weights, setWeights] = useState<ObjectiveWeights>(initial ?? DEFAULT_WEIGHTS);

  const commit = (next: ObjectiveWeights) => onCommit?.(next);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-text-secondary">
        Adjusts how the optimizer trades these off against each other. Applies on release, not
        while dragging — no live re-solve wired up yet, so this is display-only for now.
      </p>
      <div className="grid grid-cols-1 gap-x-8 gap-y-3.5 sm:grid-cols-2 lg:grid-cols-5">
        {(Object.keys(LABELS) as (keyof ObjectiveWeights)[]).map((key) => (
          <div key={key} className="flex flex-col gap-1.5">
            <div className="flex items-baseline justify-between">
              <span className="label-caps">{LABELS[key]}</span>
              <span className="font-mono text-xs tabular-nums text-accent">
                {weights[key].toFixed(1)}
              </span>
            </div>
            <input
              type="range"
              min={0}
              max={2}
              step={0.1}
              value={weights[key]}
              onChange={(e) => setWeights((w) => ({ ...w, [key]: Number(e.target.value) }))}
              onMouseUp={() => commit(weights)}
              onTouchEnd={() => commit(weights)}
              onKeyUp={() => commit(weights)}
              className="h-1.5 w-full cursor-pointer appearance-none rounded-pill bg-border accent-[#2FE0B8]"
            />
          </div>
        ))}
      </div>
    </div>
  );
}
