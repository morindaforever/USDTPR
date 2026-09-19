import { formatUsdt } from '@/utils/format';
import type { ReferralSummary } from '@/types';

interface TeamStatsProps {
  summary: ReferralSummary;
}

/** Team size statistics (§27) + commission totals (§28) — all backend data. */
export function TeamStats({ summary }: TeamStatsProps) {
  const levels = Array.from({ length: summary.max_level }, (_, i) => i + 1);

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-3 gap-3">
        <div className="rounded-2xl border border-surface-200 bg-white p-4 text-center">
          <p className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
            Direct
          </p>
          <p className="mt-1 text-xl font-bold tabular-nums text-surface-900">
            {summary.direct_referrals}
          </p>
        </div>
        <div className="rounded-2xl border border-surface-200 bg-white p-4 text-center">
          <p className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
            Total Team
          </p>
          <p className="mt-1 text-xl font-bold tabular-nums text-surface-900">
            {summary.total_team}
          </p>
        </div>
        <div className="rounded-2xl border border-surface-200 bg-white p-4 text-center">
          <p className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
            Active
          </p>
          <p className="mt-1 text-xl font-bold tabular-nums text-brand-700">
            {summary.active_team}
          </p>
        </div>
      </div>

      <div className="rounded-2xl border border-surface-200 bg-white p-4">
        <p className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
          Team by level
        </p>
        <div className="mt-2 flex flex-wrap gap-2">
          {levels.map((level) => (
            <span
              key={level}
              className="rounded-full bg-surface-50 px-3 py-1 text-xs font-semibold text-surface-700 ring-1 ring-inset ring-surface-200"
            >
              Level {level}: {summary.level_counts[String(level)] ?? 0}
            </span>
          ))}
        </div>
      </div>

      <div className="rounded-2xl border border-brand-200 bg-white p-4">
        <div className="flex items-center justify-between">
          <p className="text-sm font-semibold text-surface-900">Total Commission</p>
          <p className="text-lg font-bold tabular-nums text-brand-700">
            {formatUsdt(summary.commission_totals.total)} USDT
          </p>
        </div>
        <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-surface-500">
          <span>
            This cycle:{' '}
            <span className="font-semibold tabular-nums text-surface-800">
              {formatUsdt(summary.commission_totals.this_cycle)} USDT
            </span>
          </span>
          {levels.map((level) => (
            <span key={level}>
              Level {level}:{' '}
              <span className="font-semibold tabular-nums text-surface-800">
                {formatUsdt(summary.commission_totals.by_level[String(level)] ?? '0')} USDT
              </span>
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
