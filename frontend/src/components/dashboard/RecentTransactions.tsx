import { Link } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, ChevronRight } from 'lucide-react';
import { Card, ErrorState } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { walletService } from '@/services/walletService';
import { cn } from '@/utils/cn';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { WalletTransaction } from '@/types';

/**
 * Dashboard "Recent Transactions" (Section 13 §28): latest 5 ledger rows via
 * the existing /api/wallet/transactions/ endpoint. "View All" routes to /transactions.
 */

const TYPE_LABELS: Record<string, string> = {
  DEPOSIT: 'Deposit',
  WITHDRAWAL: 'Withdrawal',
  VIP_PURCHASE: 'VIP purchase',
  VIP_REWARD: 'Reward',
  REFERRAL_COMMISSION: 'Commission',
  WELCOME_BONUS: 'Welcome bonus',
  REFUND: 'Refund',
  ADJUSTMENT: 'Adjustment',
};

export function RecentTransactions() {
  const fetcher = () => walletService.transactions({ page: 1, page_size: 5 });
  const { data, isLoading, error, retry } = useDashboardData<{
    rows: WalletTransaction[];
  }>(async () => {
    const payload = await fetcher();
    return { rows: payload.data ?? [] };
  });

  const rows = data?.rows ?? [];

  return (
    <Card>
      <div className="p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-surface-900">Recent Transactions</h2>
          <Link
            to="/transactions"
            className="inline-flex items-center gap-0.5 text-xs font-semibold text-brand-700 hover:text-brand-800"
          >
            View All
            <ChevronRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>

        {isLoading ? (
          <div className="mt-4 space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-xl" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-2.5 w-16" />
                </div>
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="mt-4">
            <ErrorState message={error} onRetry={retry} />
          </div>
        ) : rows.length === 0 ? (
          <p className="mt-4 text-xs text-surface-500">
            No transactions yet — your wallet activity will appear here.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-surface-100">
            {rows.map((row) => {
              const isCredit = row.direction === 'CREDIT';
              return (
                <li key={row.transaction_id}>
                  <Link
                    to={`/transactions/${encodeURIComponent(row.transaction_id)}`}
                    className="flex items-center gap-3 py-2.5 transition-colors hover:opacity-80"
                  >
                    <span
                      className={cn(
                        'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl',
                        isCredit ? 'bg-emerald-50 text-emerald-600' : 'bg-surface-100 text-surface-600',
                      )}
                    >
                      {isCredit ? (
                        <ArrowDownLeft className="h-4 w-4" aria-hidden />
                      ) : (
                        <ArrowUpRight className="h-4 w-4" aria-hidden />
                      )}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-surface-900">
                        {TYPE_LABELS[row.type] ?? row.type}
                      </p>
                      <p className="text-[11px] text-surface-400">{formatDateTime(row.created_at)}</p>
                    </div>
                    <p
                      className={cn(
                        'shrink-0 text-sm font-semibold tabular-nums',
                        isCredit ? 'text-emerald-700' : 'text-surface-900',
                      )}
                    >
                      {isCredit ? '+' : '−'}
                      {formatUsdt(row.amount)}
                    </p>
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Card>
  );
}
