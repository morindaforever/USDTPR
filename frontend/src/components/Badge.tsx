import type { HTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'brand';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-200 text-surface-600 ring-surface-300',
  success: 'bg-brand-500/12 text-brand-400 ring-brand-500/30',
  warning: 'bg-accent-500/12 text-accent-600 ring-accent-500/30',
  danger: 'bg-danger-500/12 text-danger-600 ring-danger-500/30',
  info: 'bg-info-500/12 text-info-600 ring-info-500/30',
  brand: 'bg-brand-500/12 text-brand-400 ring-brand-500/30',
};

/** Compact status label used in lists, tables, and detail rows. */
export function Badge({ tone = 'neutral', className, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold',
        'ring-1 ring-inset',
        TONE_CLASSES[tone],
        className,
      )}
      {...props}
    />
  );
}
