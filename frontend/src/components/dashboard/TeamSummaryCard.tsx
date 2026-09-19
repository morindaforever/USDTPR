import { Users } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Card } from '@/components';
import { Skeleton } from '@/hooks';
import { formatUsdt } from '@/utils/format';
import type { ReferralSummary } from '@/types';

interface TeamSummaryCardProps {
  summary: ReferralSummary | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}

/**
 * Dashboard team snapshot (§42): direct/total counts plus commission
 * total, straight from the referral summary API — no local math.
 */
export function TeamSummaryCard({ summary, isLoading, error, onRetry }: TeamSummaryCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="p-5">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="mt-3 h-6 w-36" />
          <Skeleton className="mt-4 h-8 w-full rounded-xl" />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <div className="p-5 text-center">
          <p className="text-sm text-surface-600">Unable to load team information.</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-xl border border-surface-200 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
          >
            Retry
          </button>
        </div>
      </Card>
    );
  }

  if (!summary) {
    return null;
  }

  return (
    <Card>
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-surface-500">My Team</p>
            <div className="mt-1 flex items-center gap-2">
              <p className="font-display text-lg font-bold text-surface-900">
                {summary.total_team} member{summary.total_team === 1 ? '' : 's'}
              </p>
              <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
                <Users className="h-4 w-4" aria-hidden />
              </span>
            </div>
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
          <div className="rounded-xl bg-surface-50 px-2 py-2.5">
            <dt className="text-[11px] font-medium text-surface-500">Direct</dt>
            <dd className="mt-0.5 text-sm font-semibold tabular-nums text-surface-900">
              {summary.direct_referrals}
            </dd>
          </div>
          <div className="rounded-xl bg-surface-50 px-2 py-2.5">
            <dt className="text-[11px] font-medium text-surface-500">Total</dt>
            <dd className="mt-0.5 text-sm font-semibold tabular-nums text-surface-900">
              {summary.total_team}
            </dd>
          </div>
          <div className="rounded-xl bg-surface-50 px-2 py-2.5">
            <dt className="text-[11px] font-medium text-surface-500">Commission</dt>
            <dd className="mt-0.5 text-sm font-semibold tabular-nums text-brand-700">
              {formatUsdt(summary.commission_totals.total)}
            </dd>
          </div>
        </dl>

        <Link
          to="/team"
          className="mt-4 block rounded-xl bg-brand-600 px-4 py-2.5 text-center text-sm font-semibold text-white transition-colors hover:bg-brand-700"
        >
          View Team
        </Link>
      </div>
    </Card>
  );
}
