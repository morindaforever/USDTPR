import { formatUsdt } from '@/utils/format';

interface VipProgressBarProps {
  /** Rewarded total — a backend Decimal string (§22/§23: never frontend-computed). */
  rewarded: string;
  target: string;
  /** Backend-computed percent, capped at 100 server-side. */
  percent: string | number;
  label?: string;
}

/**
 * Progress bar for VIP reward tracking (Section 8 §34). All figures come
 * from the backend — the component only formats and renders.
 */
export function VipProgressBar({ rewarded, target, percent, label = 'Progress' }: VipProgressBarProps) {
  const pct = Math.max(0, Math.min(100, Number.parseFloat(String(percent)) || 0));

  return (
    <div>
      <div className="flex items-center justify-between text-xs text-surface-500">
        <span>{label}</span>
        <span className="tabular-nums">
          {formatUsdt(rewarded)} / {formatUsdt(target)} USDT · {pct.toFixed(2)}%
        </span>
      </div>
      <div
        role="progressbar"
        aria-valuenow={Math.round(pct)}
        aria-valuemin={0}
        aria-valuemax={100}
        className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-surface-100"
      >
        <div
          className="h-full rounded-full bg-brand-500 transition-[width] duration-500 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
