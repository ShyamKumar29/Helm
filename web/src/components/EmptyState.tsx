import type { ReactNode } from 'react';

interface EmptyStateProps {
  icon?: ReactNode;
  text: string;
  className?: string;
}

export function EmptyState({ icon, text, className = '' }: EmptyStateProps) {
  return (
    <div
      className={`flex flex-col items-center justify-center gap-2 py-10 text-center ${className}`}
    >
      {icon && <div className="text-text-muted text-2xl">{icon}</div>}
      <p className="text-text-muted text-sm">{text}</p>
    </div>
  );
}
