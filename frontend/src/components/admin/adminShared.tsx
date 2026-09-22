import type { ReactNode } from 'react';
import { cn } from '@/utils/cn';

/** Dark-theme admin page header. */
export function AdminPageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="font-display text-xl font-bold text-white md:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-surface-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

const BADGE_TONES: Record<string, string> = {
  PENDING: 'bg-amber-500/15 text-amber-300 ring-amber-500/30',
  APPROVED: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  COMPLETED: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  CREDITED: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  ACTIVE: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  REJECTED: 'bg-red-500/15 text-red-300 ring-red-500/30',
  BANNED: 'bg-red-500/15 text-red-300 ring-red-500/30',
  FAILED: 'bg-red-500/15 text-red-300 ring-red-500/30',
  SUSPENDED: 'bg-orange-500/15 text-orange-300 ring-orange-500/30',
  PROCESSING: 'bg-sky-500/15 text-sky-300 ring-sky-500/30',
  IN_PROGRESS: 'bg-sky-500/15 text-sky-300 ring-sky-500/30',
  OPEN: 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/30',
  RESOLVED: 'bg-sky-500/15 text-sky-300 ring-sky-500/30',
  CLOSED: 'bg-surface-200/40 text-surface-400 ring-white/10',
};

/** Status pill used across every admin list. */
export function AdminStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold ring-1 ring-inset',
        BADGE_TONES[status] ?? 'bg-surface-200/40 text-surface-300 ring-white/10',
      )}
    >
      {status.replace(/_/g, ' ').toLowerCase()}
    </span>
  );
}

/** Dashboard stat card (§7). */
export function AdminStatCard({ label, value, hint, tone = 'default' }: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'warning' | 'brand';
}) {
  return (
    <div
      className={cn(
        'rounded-2xl border p-4',
        tone === 'warning'
          ? 'border-amber-500/30 bg-amber-500/5'
          : tone === 'brand'
            ? 'border-brand-500/30 bg-brand-500/5'
            : 'border-surface-200 bg-surface-50',
      )}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wide text-surface-400">{label}</p>
      <p className="mt-1 font-display text-2xl font-bold tabular-nums text-white">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-surface-500">{hint}</p>}
    </div>
  );
}

/** Filter chip row. */
export function AdminFilterChips<T extends string>({ options, value, onChange }: {
  options: Array<{ key: T; label: string }>;
  value: T;
  onChange: (value: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <button
          key={option.key}
          type="button"
          onClick={() => onChange(option.key)}
          className={cn(
            'rounded-full px-3 py-1.5 text-xs font-semibold transition-colors',
            value === option.key
              ? 'bg-brand-600 text-white'
              : 'bg-surface-200/40 text-surface-300 hover:bg-surface-300/60',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

/** Simple bar chart for daily registrations (§9). */
export function AdminMiniBarChart({ data }: { data: Array<{ date: string; count: number }> }) {
  const max = Math.max(1, ...data.map((d) => d.count));
  if (data.length === 0) return null;
  return (
    <div className="flex h-28 items-end gap-1" role="img" aria-label="User registrations per day">
      {data.map((point) => (
        <div key={point.date} className="group relative flex-1">
          <div
            className="w-full rounded-t bg-brand-500/60 transition-colors group-hover:bg-brand-400"
            style={{ height: `${Math.max(4, (point.count / max) * 100)}%` }}
          />
          <span className="pointer-events-none absolute -top-6 left-1/2 -translate-x-1/2 rounded bg-surface-800 px-1.5 py-0.5 text-[10px] text-white opacity-0 transition-opacity group-hover:opacity-100">
            {point.date.slice(5)}: {point.count}
          </span>
        </div>
      ))}
    </div>
  );
}
