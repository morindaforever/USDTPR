import { formatDate, formatUsdt } from '@/utils/format';
import { VipProgressBar } from './VipProgressBar';
import type { VipPurchase } from '@/types';

const STATUS_TONES: Record<VipPurchase['status'], string> = {
  ACTIVE: 'bg-brand-50 text-brand-700 ring-brand-200',
  PENDING: 'bg-amber-50 text-amber-700 ring-amber-200',
  COMPLETED: 'bg-sky-50 text-sky-700 ring-sky-200',
  CANCELLED: 'bg-surface-100 text-surface-500 ring-surface-200',
};

/**
 * One purchase with backend-computed reward progress (Section 8 §33/§34).
 * All figures — rewarded, remaining, percent, next cycle — come from the
 * /vip/active/ API; this component only renders them.
 */
export function ActiveVipCard({ purchase }: { purchase: VipPurchase }) {
  const isCompleted = purchase.status === 'COMPLETED';
  const hasProgress = purchase.progress_percent !== undefined;
  const isWelcome = purchase.investment_amount === '0.00000000';

  return (
    <div className="rounded-2xl border border-brand-200 bg-white p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-base font-semibold text-surface-900">{purchase.plan_name}</h3>
          <p className="mt-0.5 text-xs text-surface-500">
            {isWelcome
              ? `Promotional — welcome reward ${formatUsdt(purchase.target_amount)} USDT (not investment profit)`
              : `${formatUsdt(purchase.investment_amount)} USDT investment`}
            {' '}
            → {formatUsdt(purchase.target_amount)} USDT target
          </p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${STATUS_TONES[purchase.status] ?? STATUS_TONES.PENDING}`}
        >
          {purchase.status}
        </span>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-xl bg-surface-50 p-3">
          <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
            Daily rate
          </dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-surface-900">
            {purchase.daily_rate_percent}%
          </dd>
        </div>
        <div className="rounded-xl bg-surface-50 p-3">
          <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
            {isCompleted ? 'Completed' : 'Started'}
          </dt>
          <dd className="mt-0.5 font-semibold text-surface-900">
            {isCompleted
              ? purchase.completed_at
                ? formatDate(purchase.completed_at)
                : '—'
              : purchase.started_at
                ? formatDate(purchase.started_at)
                : '—'}
          </dd>
        </div>
      </dl>

      {hasProgress ? (
        <div className="mt-3">
          <VipProgressBar
            rewarded={purchase.rewarded_amount ?? '0'}
            target={purchase.target_amount}
            percent={purchase.progress_percent ?? '0'}
            label={isCompleted ? (isWelcome ? 'Welcome reward credited' : 'Total rewarded') : 'Progress'}
          />
          {!isCompleted && purchase.next_reward_cycle && (
            <p className="mt-2 text-[11px] leading-relaxed text-surface-500">
              Next reward cycle: {formatDate(purchase.next_reward_cycle)} · credited automatically
              by the daily reward run. Terms shown are the plan snapshot taken at purchase.
            </p>
          )}
          {isCompleted && (
            <p className="mt-2 text-[11px] leading-relaxed text-surface-500">
              Target reached — this plan is complete and no longer accrues rewards.
            </p>
          )}
        </div>
      ) : (
        <p className="mt-3 text-[11px] leading-relaxed text-surface-500">
          Reward tracking starts in the next system cycle. Terms shown are the plan snapshot taken
          at purchase.
        </p>
      )}
    </div>
  );
}
