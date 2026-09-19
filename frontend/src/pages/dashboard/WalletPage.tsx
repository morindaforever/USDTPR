import { PageContainer } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { walletService } from '@/services/walletService';
import { TransactionHistory } from '@/components/wallet';
import { formatUsdt } from '@/utils/format';
import type { WalletSummary } from '@/types';

const BUCKET_ROWS: Array<{ key: keyof WalletSummary; label: string; hint: string }> = [
  { key: 'deposit_balance', label: 'Deposit balance', hint: 'Credited from approved deposits' },
  { key: 'withdrawable_balance', label: 'Withdrawable', hint: 'Eligible for withdrawal requests' },
  { key: 'bonus_balance', label: 'Bonus balance', hint: 'From rewards and bonuses' },
  { key: 'pending_balance', label: 'Pending', hint: 'Awaiting confirmation' },
  { key: 'locked_balance', label: 'Locked', hint: 'Reserved for in-flight operations' },
];

/**
 * Optional wallet detail page (Section 5): balances + ledger history.
 * Read-only; mutations remain backend-internal.
 */
export function WalletPage() {
  const { data: summary, isLoading, error, retry } = useDashboardData<WalletSummary>(
    () => walletService.summary(),
  );

  return (
    <PageContainer title="Wallet" subtitle="Balances and complete ledger history.">
      <div className="space-y-6">
        {/* Summary */}
        <section aria-labelledby="balances-heading">
          <h2 id="balances-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Balances
          </h2>
          {isLoading ? (
            <div className="rounded-2xl border border-surface-200 bg-white p-5">
              <Skeleton className="h-8 w-40" />
              <div className="mt-4 space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            </div>
          ) : error || !summary ? (
            <div className="rounded-2xl border border-surface-200 bg-white p-5 text-center">
              <p className="text-sm text-surface-600">Unable to load wallet information.</p>
              <button
                type="button"
                onClick={retry}
                className="mt-3 rounded-xl border border-surface-200 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="overflow-hidden rounded-2xl border border-surface-200 bg-white">
              <div className="border-b border-surface-100 bg-surface-950 p-5 text-white">
                <p className="text-xs font-medium uppercase tracking-wide text-surface-400">
                  Total balance
                </p>
                <div className="mt-1 flex items-baseline gap-2">
                  <span className="font-display text-3xl font-bold tabular-nums">
                    {formatUsdt(summary.total_balance)}
                  </span>
                  <span className="text-sm font-semibold text-surface-400">USDT</span>
                </div>
              </div>
              <dl className="divide-y divide-surface-100">
                {BUCKET_ROWS.map(({ key, label, hint }) => (
                  <div key={key} className="flex items-center justify-between px-4 py-3">
                    <dt>
                      <p className="text-sm font-medium text-surface-900">{label}</p>
                      <p className="text-[11px] text-surface-500">{hint}</p>
                    </dt>
                    <dd className="text-sm font-semibold tabular-nums text-surface-900">
                      {formatUsdt(summary[key])}{' '}
                      <span className="text-[11px] font-medium text-surface-500">USDT</span>
                    </dd>
                  </div>
                ))}
              </dl>
              <p className="border-t border-surface-100 bg-surface-50 px-4 py-2.5 text-[11px] leading-relaxed text-surface-500">
                Total = deposit + withdrawable + bonus + pending + locked. Every balance change is
                recorded in the ledger below; balances update only through completed ledger
                transactions.
              </p>
            </div>
          )}
        </section>

        <TransactionHistory />
      </div>
    </PageContainer>
  );
}
