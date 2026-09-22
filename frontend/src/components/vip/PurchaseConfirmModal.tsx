import { formatUsdt } from '@/utils/format';
import type { PlanPurchaseSummary } from '@/types';

export interface PurchaseConfirmModalProps {
  open: boolean;
  summary: PlanPurchaseSummary | null;
  /** Loading state while the summary request is in flight. */
  isLoading: boolean;
  /** True while the purchase request is processing (disables confirm). */
  isPurchasing: boolean;
  errorMessage: string | null;
  onConfirm: () => void;
  onClose: () => void;
}

/**
 * Purchase confirmation. Every number shown comes from the backend summary
 * endpoint — the frontend never computes authoritative amounts.
 */
export function PurchaseConfirmModal({
  open,
  summary,
  isLoading,
  isPurchasing,
  errorMessage,
  onConfirm,
  onClose,
}: PurchaseConfirmModalProps) {
  if (!open) return null;

  const plan = summary?.plan;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-black/60 p-0 sm:items-center sm:p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="purchase-confirm-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-t-3xl bg-surface-50 p-5 shadow-xl sm:rounded-3xl sm:p-6"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="purchase-confirm-title" className="text-lg font-semibold text-surface-800">
          Confirm VIP Purchase
        </h2>
        <p className="mt-1 text-sm text-surface-500">
          Plan terms are configuration values.
        </p>

        {isLoading ? (
          <div className="mt-5 space-y-3">
            <div className="h-12 animate-pulse rounded-xl bg-surface-100" />
            <div className="h-12 animate-pulse rounded-xl bg-surface-100" />
            <div className="h-12 animate-pulse rounded-xl bg-surface-100" />
          </div>
        ) : !summary || !plan ? (
          <p className="mt-5 rounded-xl bg-surface-50 p-4 text-sm text-surface-600">
            Plan details are unavailable. Please close and try again.
          </p>
        ) : (
          <dl className="mt-5 space-y-2.5 rounded-2xl bg-surface-50 p-4 text-sm">
            <div className="flex items-center justify-between">
              <dt className="text-surface-500">Plan</dt>
              <dd className="font-semibold text-surface-800">{plan.name}</dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-surface-500">Investment</dt>
              <dd className="font-semibold tabular-nums text-surface-800">
                {Number(plan.investment_amount) === 0
                  ? 'Free — 0 USDT'
                  : `${formatUsdt(plan.investment_amount)} USDT`}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-surface-500">
                {Number(plan.investment_amount) === 0 ? 'Welcome Reward Target' : 'Target'}
              </dt>
              <dd className="font-semibold tabular-nums text-surface-800">
                {formatUsdt(plan.target_amount)} USDT
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-surface-500">Daily Return</dt>
              <dd className="font-semibold tabular-nums text-brand-400">
                {plan.daily_rate_percent}%
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-surface-500">Daily Reward</dt>
              <dd className="font-semibold tabular-nums text-brand-400">
                {formatUsdt(
                  (Number(plan.target_amount) * Number(plan.daily_rate)).toFixed(2),
                )}{' '}
                USDT
              </dd>
            </div>
            {Number(plan.investment_amount) === 0 && (
              <p className="rounded-xl bg-accent-200 px-3 py-2 text-[11px] leading-relaxed text-amber-800">
                Promotional welcome reward — accrues daily from the next reward cycle
                until the reward target is reached. Nothing is spent or credited at
                claim time. Not investment profit. Does not unlock withdrawals.
              </p>
            )}
            <div className="my-2 border-t border-surface-200" />
            <div className="flex items-center justify-between">
              <dt className="text-surface-500">Available (deposit + withdrawable)</dt>
              <dd className="font-semibold tabular-nums text-surface-800">
                {formatUsdt(summary.available_balance)} USDT
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt className="text-surface-500">Balance after purchase</dt>
              <dd
                className={`font-semibold tabular-nums ${
                  summary.sufficient ? 'text-surface-800' : 'text-danger-600'
                }`}
              >
                {formatUsdt(summary.balance_after_purchase)} USDT
              </dd>
            </div>
          </dl>
        )}

        {errorMessage && (
          <p role="alert" className="mt-3 rounded-xl bg-danger-50 p-3 text-sm text-danger-700">
            {errorMessage}
          </p>
        )}

        <div className="mt-5 flex gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isPurchasing}
            className="flex-1 rounded-xl border border-surface-200 px-4 py-2.5 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isPurchasing || isLoading || !summary?.sufficient}
            className="flex-1 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-surface-800 shadow-sm transition-colors hover:bg-brand-700 active:bg-brand-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isPurchasing
              ? 'Processing…'
              : Number(plan?.investment_amount) === 0
                ? 'Claim Welcome Reward'
                : 'Confirm Purchase'}
          </button>
        </div>
        {!isLoading && summary && !summary.sufficient && (
          <p className="mt-2 text-center text-xs text-surface-500">
            Insufficient combined balance (deposit + withdrawable) for this plan.
          </p>
        )}
        {!isLoading && summary && Number(plan?.investment_amount) === 0 && (
          <p className="mt-2 text-center text-xs text-surface-500">
            No wallet balance is required — nothing is spent when claiming; daily
            rewards begin with the next reward cycle.
          </p>
        )}
      </div>
    </div>
  );
}
