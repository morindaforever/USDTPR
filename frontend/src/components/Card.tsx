import type { HTMLAttributes } from 'react';
import { cn } from '@/utils/cn';

export interface CardProps extends HTMLAttributes<HTMLDivElement> {
  /** Renders an emerald emphasis treatment for the selected/active card. */
  highlight?: boolean;
}

/** Base surface for grouped content — the workhorse of the dashboard. */
export function Card({ className, highlight = false, ...props }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-2xl border border-surface-200 bg-surface-50',
        highlight && 'border-brand-500/40 bg-brand-950/20 ring-1 ring-brand-500/20',
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex flex-col gap-1 border-b border-surface-200 px-4 py-3.5', className)}
      {...props}
    />
  );
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn('text-sm font-semibold text-surface-800', className)}
      {...props}
    />
  );
}

export function CardDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-xs text-surface-500', className)} {...props} />;
}

export function CardContent({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-4 py-4', className)} {...props} />;
}

export function CardFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn('flex items-center gap-2 border-t border-surface-200 px-4 py-3', className)}
      {...props}
    />
  );
}
