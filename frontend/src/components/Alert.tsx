import type { ReactNode } from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  XCircle,
  type LucideIcon,
} from 'lucide-react';
import { cn } from '@/utils/cn';

type AlertTone = 'info' | 'success' | 'warning' | 'danger';

export interface AlertProps {
  tone?: AlertTone;
  title?: string;
  children?: ReactNode;
  className?: string;
}

const TONE_CONFIG: Record<AlertTone, { icon: LucideIcon; classes: string }> = {
  info: { icon: Info, classes: 'bg-sky-50 text-sky-900 ring-sky-200' },
  success: { icon: CheckCircle2, classes: 'bg-emerald-50 text-emerald-900 ring-emerald-200' },
  warning: { icon: AlertTriangle, classes: 'bg-accent-50 text-accent-900 ring-accent-200' },
  danger: { icon: XCircle, classes: 'bg-red-50 text-red-900 ring-red-200' },
};

/** Inline feedback banner for form results, notices, and system messages. */
export function Alert({ tone = 'info', title, children, className }: AlertProps) {
  const { icon: Icon, classes } = TONE_CONFIG[tone];
  return (
    <div
      role="alert"
      className={cn('flex gap-3 rounded-xl p-3.5 ring-1 ring-inset', classes, className)}
    >
      <Icon className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
      <div className="text-sm">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className={cn(title && 'mt-0.5', 'opacity-90')}>{children}</div>}
      </div>
    </div>
  );
}
