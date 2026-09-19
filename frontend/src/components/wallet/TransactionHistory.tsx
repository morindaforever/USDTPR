import { useCallback, useEffect, useState } from 'react';
import { ArrowDownLeft, ArrowUpRight, ChevronLeft, ChevronRight } from 'lucide-react';
import { Badge, Card } from '@/components';
import { Skeleton } from '@/hooks';
import { walletService } from '@/services/walletService';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { PaginationMeta, TransactionFilters, WalletTransaction } from '@/types';

const PAGE_SIZE = 10;

const TYPE_OPTIONS = [
  { value: '', label: 'All types' },
  { value: 'DEPOSIT', label: 'Deposits' },
  { value: 'WITHDRAWAL', label: 'Withdrawals' },
  { value: 'VIP_PURCHASE', label: 'VIP purchases' },
  { value: 'VIP_REWARD', label: 'Rewards' },
  { value: 'REFERRAL_COMMISSION', label: 'Commissions' },
  { value: 'ADJUSTMENT', label: 'Adjustments' },
  { value: 'LOCK', label: 'Locks' },
  { value: 'RELEASE', label: 'Releases' },
] as const;

const STATUS_OPTIONS = [
  { value: '', label: 'All statuses' },
  { value: 'COMPLETED', label: 'Completed' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'REVERSED', label: 'Reversed' },
] as const;

function typeLabel(type: string): string {
  const labels: Record<string, string> = {
    DEPOSIT: 'Deposit',
    WITHDRAWAL: 'Withdrawal',
    VIP_PURCHASE: 'VIP purchase',
    VIP_REWARD: 'Reward',
    REFERRAL_COMMISSION: 'Commission',
    WELCOME_BONUS: 'Welcome bonus',
    REFUND: 'Refund',
    ADJUSTMENT: 'Adjustment',
    LOCK: 'Lock',
    RELEASE: 'Release',
    TRANSFER: 'Transfer',
  };
  return labels[type] ?? type;
}

function statusTone(status: string): 'success' | 'warning' | 'neutral' | 'danger' {
  if (status === 'COMPLETED') return 'success';
  if (status === 'PENDING') return 'warning';
  if (status === 'REVERSED') return 'neutral';
  return 'danger';
}

interface HistoryState {
  rows: WalletTransaction[];
  pagination: PaginationMeta | null;
  isLoading: boolean;
  error: string | null;
}

/** Paginated ledger history with type/status/direction/date filters. */
export function TransactionHistory() {
  const [filters, setFilters] = useState<TransactionFilters>({ page: 1, page_size: PAGE_SIZE });
  const [state, setState] = useState<HistoryState>({
    rows: [],
    pagination: null,
    isLoading: true,
    error: null,
  });

  const load = useCallback(async (current: TransactionFilters) => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const payload = await walletService.transactions(current);
      setState({
        rows: payload.data ?? [],
        pagination: payload.pagination ?? null,
        isLoading: false,
        error: null,
      });
    } catch (err) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: err instanceof Error ? err.message : 'Unable to load transactions.',
      }));
    }
  }, []);

  useEffect(() => {
    void load(filters);
  }, [filters, load]);

  const update = (patch: Partial<TransactionFilters>) =>
    setFilters((prev) => ({ ...prev, ...patch, page: patch.page ?? 1 }));

  const pagination = state.pagination;

  return (
    <section aria-labelledby="history-heading">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="history-heading" className="text-sm font-semibold text-surface-900">
          Transaction history
        </h2>
        {pagination && (
          <span className="text-xs text-surface-500">
            {pagination.count} transaction{pagination.count === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {/* Filters */}
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <select
          aria-label="Filter by type"
          value={filters.type ?? ''}
          onChange={(e) => update({ type: e.target.value || undefined })}
          className="rounded-xl border border-surface-200 bg-white px-3 py-2 text-xs font-medium text-surface-700 focus:border-brand-500 focus:outline-none"
        >
          {TYPE_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <select
          aria-label="Filter by status"
          value={filters.status ?? ''}
          onChange={(e) => update({ status: e.target.value || undefined })}
          className="rounded-xl border border-surface-200 bg-white px-3 py-2 text-xs font-medium text-surface-700 focus:border-brand-500 focus:outline-none"
        >
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <select
          aria-label="Filter by direction"
          value={filters.direction ?? ''}
          onChange={(e) => update({ direction: e.target.value || undefined })}
          className="rounded-xl border border-surface-200 bg-white px-3 py-2 text-xs font-medium text-surface-700 focus:border-brand-500 focus:outline-none"
        >
          <option value="">All directions</option>
          <option value="CREDIT">Credits only</option>
          <option value="DEBIT">Debits only</option>
        </select>
        <input
          type="date"
          aria-label="From date"
          value={filters.date_from ?? ''}
          onChange={(e) => update({ date_from: e.target.value || undefined })}
          className="rounded-xl border border-surface-200 bg-white px-3 py-2 text-xs font-medium text-surface-700 focus:border-brand-500 focus:outline-none"
        />
      </div>

      <Card>
        {state.isLoading ? (
          <div className="space-y-3 p-4">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : state.error ? (
          <div className="p-5 text-center">
            <p className="text-sm text-surface-600">{state.error}</p>
            <button
              type="button"
              onClick={() => void load(filters)}
              className="mt-3 rounded-xl border border-surface-200 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
            >
              Retry
            </button>
          </div>
        ) : state.rows.length === 0 ? (
          <div className="px-4 py-10 text-center">
            <p className="text-sm font-medium text-surface-900">No transactions found</p>
            <p className="mt-1 text-xs text-surface-500">
              Ledger entries appear here once deposits, rewards, or adjustments occur.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-surface-100">
            {state.rows.map((row) => {
              const isCredit = row.direction === 'CREDIT';
              return (
                <li key={row.transaction_id} className="flex items-center gap-3 px-4 py-3">
                  <span
                    className={
                      isCredit
                        ? 'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600'
                        : 'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-surface-100 text-surface-600'
                    }
                  >
                    {isCredit ? (
                      <ArrowDownLeft className="h-4 w-4" aria-hidden />
                    ) : (
                      <ArrowUpRight className="h-4 w-4" aria-hidden />
                    )}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <p className="truncate text-sm font-semibold text-surface-900">
                        {typeLabel(row.type)}
                      </p>
                      <Badge tone={statusTone(row.status)}>{row.status.toLowerCase()}</Badge>
                    </div>
                    <p className="truncate text-[11px] text-surface-500">
                      {row.description || '—'} · {formatDateTime(row.created_at)}
                    </p>
                  </div>
                  {/* Sign carries the direction, color is only reinforcement. */}
                  <p
                    className={`text-sm font-semibold tabular-nums ${
                      isCredit ? 'text-emerald-700' : 'text-surface-900'
                    }`}
                  >
                    {isCredit ? '+' : '−'}
                    {formatUsdt(row.amount)}{' '}
                    <span className="text-[11px] font-medium text-surface-500">USDT</span>
                  </p>
                </li>
              );
            })}
          </ul>
        )}

        {/* Pagination */}
        {pagination && pagination.pages > 1 && !state.isLoading && !state.error && (
          <div className="flex items-center justify-between border-t border-surface-100 px-4 py-3">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => update({ page: pagination.page - 1 })}
              className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-xs font-semibold text-surface-700 transition-colors hover:bg-surface-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
              Prev
            </button>
            <span className="text-xs text-surface-500">
              Page {pagination.page} of {pagination.pages}
            </span>
            <button
              type="button"
              disabled={pagination.page >= pagination.pages}
              onClick={() => update({ page: pagination.page + 1 })}
              className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-xs font-semibold text-surface-700 transition-colors hover:bg-surface-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next
              <ChevronRight className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        )}
      </Card>
    </section>
  );
}
