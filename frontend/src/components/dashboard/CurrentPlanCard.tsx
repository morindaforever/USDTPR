import { Crown, TrendingUp } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge, Card } from '@/components';
import { Skeleton } from '@/hooks';
import { RewardCountdown } from './RewardCountdown';
import { formatUsdt } from '@/utils/format';
import type { CurrentPlan } from '@/types';

interface CurrentPlanCardProps {
  plan: CurrentPlan | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}

/**
 * Read-only view of the active VIP purchase (backend snapshot data). All
 * progress figures — including the next-reward schedule — come from the
 * backend reward engine; this component never computes credited amounts.
 * The "daily reward" shown is the configured plan rate applied to the
 * snapshot target (target_amount × daily_rate_snapshot), i.e. the plan's
 * configured daily cycle, not a balance calculation.
 */
export function CurrentPlanCard({ plan, isLoading, error, onRetry }: CurrentPlanCardProps) {
  if (isLoading) {
    return (
      <Card>
        <div className="p-5">
          <Skeleton className="h-3 w-24" />
          <Skeleton className="mt-3 h-6 w-32" />
          <Skeleton className="mt-4 h-2 w-full" />
          <Skeleton className="mt-4 h-11 w-full rounded-xl" />
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card>
        <div className="p-5 text-center">
          <p className="text-sm text-surface-500">Unable to load plan information.</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-xl border border-surface-300 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-200"
          >
            Retry
          </button>
        </div>
      </Card>
    );
  }

  if (!plan) {
    return (
      <Card>
        <div className="flex flex-col items-center gap-2 p-6 text-center">
          <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-accent-500/12 text-accent-600">
            <Crown className="h-5 w-5" aria-hidden />
          </span>
          <p className="text-sm font-semibold text-surface-800">No active plan</p>
          <p className="max-w-xs text-xs leading-relaxed text-surface-500">
            Explore available plans to get started.
          </p>
          <Link
            to="/vip"
            className="mt-2 rounded-xl bg-brand-500 px-4 py-2 text-sm font-semibold text-white shadow-glow transition-colors hover:bg-brand-400"
          >
            View VIP Plans
          </Link>
        </div>
      </Card>
    );
  }

  const percent = Number.parseFloat(plan.progress_percent ?? '0') || 0;
  const rewarded = plan.rewarded_amount ?? plan.amount_received;
  const dailyConfigured =
    Number.parseFloat(plan.target_amount) * Number.parseFloat(plan.daily_rate_snapshot || '0');

  return (
    <Card>
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="eyebrow">Current plan</p>
            <div className="mt-1.5 flex items-center gap-2">
              <p className="font-display text-lg font-bold tracking-tight text-surface-800">
                {plan.plan_name_snapshot}
              </p>
              {plan.is_welcome_plan ? <Badge tone="warning">Promotional</Badge> : <Badge tone="success">Active</Badge>}
            </div>
          </div>
          <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-accent-500/12 text-accent-600">
            <Crown className="h-5 w-5" aria-hidden />
          </span>
        </div>

        <dl className="mt-4 grid grid-cols-3 gap-2">
          <div className="rounded-xl border border-surface-200 bg-surface-900/50 px-2 py-2.5 text-center">
            <dt className="text-[11px] font-medium text-surface-500">Investment</dt>
            <dd className="figure mt-0.5 text-sm text-surface-700">
              {formatUsdt(plan.investment_amount)}
            </dd>
          </div>
          <div className="rounded-xl border border-surface-200 bg-surface-900/50 px-2 py-2.5 text-center">
            <dt className="text-[11px] font-medium text-surface-500">Target</dt>
            <dd className="figure mt-0.5 text-sm text-surface-700">
              {formatUsdt(plan.target_amount)}
            </dd>
          </div>
          <div className="rounded-xl border border-brand-500/20 bg-brand-500/5 px-2 py-2.5 text-center">
            <dt className="text-[11px] font-medium text-brand-400/80">Daily reward</dt>
            <dd className="figure mt-0.5 text-sm text-brand-400">
              {dailyConfigured > 0 ? formatUsdt(String(dailyConfigured)) : '—'}
            </dd>
          </div>
        </dl>

        <div className="mt-5">
          <div className="mb-1.5 flex items-center justify-between text-xs">
            <span className="inline-flex items-center gap-1 font-medium text-surface-500">
              <TrendingUp className="h-3.5 w-3.5 text-brand-400" aria-hidden />
              Progress
            </span>
            <span className="font-semibold tabular-nums text-surface-600">
              {formatUsdt(rewarded)} / {formatUsdt(plan.target_amount)} USDT · {percent.toFixed(1)}%
            </span>
          </div>
          <div
            role="progressbar"
            aria-valuenow={Math.round(percent)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-2 w-full overflow-hidden rounded-full bg-surface-200"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-brand-500 to-brand-400 transition-[width] duration-500 ease-out"
              style={{ width: `${Math.min(100, Math.max(0, percent))}%` }}
            />
          </div>
        </div>

        {plan.next_reward_at && <RewardCountdown nextRewardAt={plan.next_reward_at} />}
      </div>
    </Card>
  );
}
