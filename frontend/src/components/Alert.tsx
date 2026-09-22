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
  info: { icon: Info, classes: 'bg-info-500/10 text-info-700 ring-info-500/25' },
  success: { icon: CheckCircle2, classes: 'bg-brand-500/10 text-brand-400 ring-brand-500/25' },
  warning: { icon: AlertTriangle, classes: 'bg-accent-500/10 text-accent-700 ring-accent-500/25' },
  danger: { icon: XCircle, classes: 'bg-danger-500/10 text-danger-600 ring-danger-500/25' },
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
