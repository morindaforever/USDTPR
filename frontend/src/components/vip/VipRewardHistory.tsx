import { formatDate, formatUsdt } from '@/utils/format';
import type { VipReward } from '@/types';

const STATUS_TONES: Record<VipReward['status'], string> = {
  PENDING: 'bg-amber-50 text-amber-700 ring-amber-200',
  COMPLETED: 'bg-brand-50 text-brand-700 ring-brand-200',
  FAILED: 'bg-red-50 text-red-700 ring-red-200',
  REVERSED: 'bg-surface-100 text-surface-500 ring-surface-200',
};

/**
 * Reward history list (Section 8 §36): one row per reward cycle. Every
 * amount/status/transaction reference comes straight from the backend.
 */
export function VipRewardHistory({ rewards }: { rewards: VipReward[] }) {
  if (rewards.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-surface-200 p-5 text-center text-sm text-surface-500">
        No rewards yet. Your reward history will appear here after an eligible reward cycle is
        processed.
      </p>
    );
  }

  return (
    <ul className="space-y-2.5">
      {rewards.map((reward) => (
        <li
          key={reward.reward_id}
          className="flex items-center justify-between gap-3 rounded-2xl border border-surface-200 bg-white p-4"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-surface-900">
              {reward.plan_name}
              <span className="ml-2 text-[11px] font-normal text-surface-400">
                {reward.reward_id}
              </span>
            </p>
            <p className="mt-0.5 truncate text-xs text-surface-500">
              {formatDate(reward.reward_date)} ·{' '}
              {reward.transaction_id ? (
                <span className="font-mono">{reward.transaction_id}</span>
              ) : (
                'No transaction'
              )}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-sm font-semibold tabular-nums text-brand-700">
              +{formatUsdt(reward.credited_amount)} USDT
            </p>
            <span
              className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${STATUS_TONES[reward.status] ?? STATUS_TONES.PENDING}`}
            >
              {reward.status}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
