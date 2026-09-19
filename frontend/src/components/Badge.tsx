import type { HTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

type BadgeTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'brand';

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
}

const TONE_CLASSES: Record<BadgeTone, string> = {
  neutral: 'bg-surface-100 text-surface-700 ring-surface-200',
  success: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  warning: 'bg-accent-50 text-accent-700 ring-accent-200',
  danger: 'bg-red-50 text-red-700 ring-red-200',
  info: 'bg-sky-50 text-sky-700 ring-sky-200',
  brand: 'bg-brand-50 text-brand-700 ring-brand-200',
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
