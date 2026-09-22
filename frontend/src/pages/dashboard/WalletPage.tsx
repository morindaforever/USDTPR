import { ArrowDownToLine, ArrowUpFromLine } from 'lucide-react';
import { Link } from 'react-router-dom';
import { PageContainer } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { walletService } from '@/services/walletService';
import { TransactionHistory } from '@/components/wallet';
import { formatUsdt } from '@/utils/format';
import { cn } from '@/utils/cn';
import type { WalletSummary } from '@/types';

const BUCKET_ROWS: Array<{ key: keyof WalletSummary; label: string; hint: string; accent?: boolean }> = [
  { key: 'deposit_balance', label: 'Deposit balance', hint: 'Credited from approved deposits' },
  { key: 'withdrawable_balance', label: 'Withdrawable', hint: 'Eligible for withdrawal requests', accent: true },
  { key: 'bonus_balance', label: 'Bonus balance', hint: 'From rewards and bonuses' },
  { key: 'pending_balance', label: 'Pending', hint: 'Awaiting confirmation' },
  { key: 'locked_balance', label: 'Locked', hint: 'Reserved for in-flight operations' },
];

/**
 * Wallet detail page: balances + ledger history. Read-only; mutations remain
 * backend-internal.
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
          <h2 id="balances-heading" className="eyebrow mb-3">
            Balances
          </h2>
          {isLoading ? (
            <div className="rounded-2xl border border-surface-200 bg-surface-50 p-6">
              <Skeleton className="h-10 w-48" />
              <div className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <Skeleton className="h-20 rounded-xl" />
                <Skeleton className="h-20 rounded-xl" />
                <Skeleton className="h-20 rounded-xl" />
                <Skeleton className="h-20 rounded-xl" />
              </div>
            </div>
          ) : error || !summary ? (
            <div className="rounded-2xl border border-surface-200 bg-surface-50 p-6 text-center">
              <p className="text-sm text-surface-500">Unable to load wallet information.</p>
              <button
                type="button"
                onClick={retry}
                className="mt-3 rounded-xl border border-surface-300 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-200"
              >
                Retry
              </button>
            </div>
          ) : (
            <>
              <div className="relative overflow-hidden rounded-2xl border border-surface-200 bg-surface-50 p-6 shadow-card">
                <div aria-hidden className="bg-grid pointer-events-none absolute inset-0 opacity-60" />
                <div
                  aria-hidden
                  className="pointer-events-none absolute -right-20 -top-24 h-56 w-56 rounded-full bg-brand-500/10 blur-3xl"
                />
                <div className="relative">
                  <p className="eyebrow">Total balance</p>
                  <div className="mt-2 flex items-baseline gap-2.5">
                    <span className="figure text-3xl text-surface-800 md:text-4xl">
                      {formatUsdt(summary.total_balance)}
                    </span>
                    <span className="text-sm font-semibold text-brand-400">USDT</span>
                  </div>
                  <div className="mt-5 flex flex-wrap gap-2.5">
                    <Link
                      to="/deposit"
                      className="inline-flex h-10 items-center gap-2 rounded-xl bg-brand-500 px-4 text-sm font-semibold text-white shadow-glow transition-colors hover:bg-brand-400"
                    >
                      <ArrowDownToLine className="h-4 w-4" aria-hidden />
                      Deposit
                    </Link>
                    <Link
                      to="/withdraw"
                      className="inline-flex h-10 items-center gap-2 rounded-xl border border-surface-300 px-4 text-sm font-semibold text-surface-700 transition-colors hover:border-surface-400 hover:bg-surface-100"
                    >
                      <ArrowUpFromLine className="h-4 w-4" aria-hidden />
                      Withdraw
                    </Link>
                  </div>
                </div>
              </div>

              <dl className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                {BUCKET_ROWS.map(({ key, label, hint, accent }) => (
                  <div
                    key={key}
                    className={cn(
                      'rounded-xl border px-4 py-3.5',
                      accent
                        ? 'border-brand-500/20 bg-brand-500/5'
                        : 'border-surface-200 bg-surface-50',
                    )}
                  >
                    <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
                      {label}
                    </dt>
                    <dd
                      className={cn(
                        'figure mt-1 text-base',
                        accent ? 'text-brand-400' : 'text-surface-700',
                      )}
                    >
                      {formatUsdt(summary[key])}
                    </dd>
                    <p className="mt-1 text-[11px] leading-snug text-surface-500">{hint}</p>
                  </div>
                ))}
              </dl>

              <p className="mt-3 text-[11px] leading-relaxed text-surface-500">
                Total = deposit + withdrawable + bonus + pending + locked. Every balance change is
                recorded in the ledger below; balances update only through completed ledger
                transactions.
              </p>
            </>
          )}
        </section>

        <TransactionHistory />
      </div>
    </PageContainer>
  );
}
