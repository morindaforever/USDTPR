import type { ComponentType, ReactNode } from 'react';
import { Inbox } from 'lucide-react';

export interface EmptyStateProps {
  icon?: ComponentType<{ className?: string }>;
  title: string;
  description?: string;
  action?: ReactNode;
}

/** Shown when a list or section has nothing to display yet. */
export function EmptyState({ icon: Icon = Inbox, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-surface-200 bg-surface-50/60 px-6 py-10 text-center">
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-surface-100 text-surface-400">
        <Icon className="h-5 w-5" aria-hidden />
      </div>
      <p className="text-sm font-semibold text-surface-900">{title}</p>
      {description && <p className="max-w-xs text-xs text-surface-500">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
