import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, ChevronLeft, ChevronRight } from 'lucide-react';
import { Badge, Card, ErrorState, PageContainer } from '@/components';
import { useDashboardData } from '@/hooks';
import { walletService } from '@/services/walletService';
import { cn } from '@/utils/cn';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { PaginationMeta, TransactionFilters, WalletTransaction } from '@/types';

const PAGE_SIZE = 15;

/**
 * Unified transaction history (Section 13 §20–23). READS THE EXISTING
 * WalletTransaction LEDGER via /api/wallet/transactions/ — no second
 * accounting system, no per-model recombination. Filters, search, and
 * pagination are all server-side (§35).
 */

const TYPE_OPTIONS = [
  { value: '', label: 'All' },
  { value: 'DEPOSIT', label: 'Deposits' },
  { value: 'WITHDRAWAL', label: 'Withdrawals' },
  { value: 'VIP_REWARD', label: 'Rewards' },
  { value: 'VIP_PURCHASE', label: 'VIP' },
  { value: 'REFERRAL_COMMISSION', label: 'Referral' },
] as const;

const STATUS_OPTIONS = ['COMPLETED', 'PENDING', 'REVERSED', 'FAILED'] as const;

const TYPE_LABELS: Record<string, string> = {
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
};

function typeLabel(type: string): string {
  return TYPE_LABELS[type] ?? type;
}

function statusTone(status: string): 'success' | 'warning' | 'neutral' | 'danger' {
  if (status === 'COMPLETED') return 'success';
  if (status === 'PENDING') return 'warning';
  if (status === 'REVERSED') return 'neutral';
  return 'danger';
}

/** Row content shared by the desktop table and the mobile card list (§21). */
function TransactionRow({ row }: { row: WalletTransaction }) {
  const isCredit = row.direction === 'CREDIT';
  return (
    <Link
      to={`/transactions/${encodeURIComponent(row.transaction_id)}`}
      className="block transition-colors hover:bg-surface-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600"
    >
      {/* Mobile card layout — no horizontal overflow at 320px (§3, §45). */}
      <div className="flex items-center gap-3 px-4 py-3 md:hidden">
        <span
          className={cn(
            'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl',
            isCredit ? 'bg-brand-500/10 text-brand-400' : 'bg-surface-100 text-surface-600',
          )}
        >
          {isCredit ? (
            <ArrowDownLeft className="h-4 w-4" aria-hidden />
          ) : (
            <ArrowUpRight className="h-4 w-4" aria-hidden />
          )}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-surface-800">{typeLabel(row.type)}</p>
            <Badge tone={statusTone(row.status)}>{row.status.toLowerCase()}</Badge>
          </div>
          <p className="mt-0.5 truncate text-[11px] text-surface-500">{formatDateTime(row.created_at)}</p>
        </div>
        <p
          className={cn(
            'shrink-0 text-sm font-semibold tabular-nums',
            isCredit ? 'text-brand-400' : 'text-surface-800',
          )}
        >
          {isCredit ? '+' : '−'}
          {formatUsdt(row.amount)}
        </p>
      </div>

      {/* Desktop row. */}
      <div className="hidden items-center gap-4 px-4 py-3 md:flex">
        <div className="w-44 min-w-0">
          <p className="truncate text-sm font-semibold text-surface-800">{typeLabel(row.type)}</p>
          <p className="truncate text-[11px] text-surface-400">{row.transaction_id}</p>
        </div>
        <p
          className={cn(
            'w-36 shrink-0 text-sm font-semibold tabular-nums',
            isCredit ? 'text-brand-400' : 'text-surface-800',
          )}
        >
          {isCredit ? '+' : '−'}
          {formatUsdt(row.amount)} <span className="text-[11px] text-surface-400">USDT</span>
        </p>
        <div className="w-24 shrink-0">
          <Badge tone={statusTone(row.status)}>{row.status.toLowerCase()}</Badge>
        </div>
        <p className="min-w-0 flex-1 truncate text-xs text-surface-500">{row.description || '—'}</p>
        <p className="shrink-0 text-xs tabular-nums text-surface-500">{formatDateTime(row.created_at)}</p>
      </div>
    </Link>
  );
}

interface ListState {
  rows: WalletTransaction[];
  pagination: PaginationMeta | null;
}

export function TransactionsPage() {
  const [type, setType] = useState('');
  const [status, setStatus] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const fetcher = async (): Promise<ListState> => {
    const filters: TransactionFilters = { page, page_size: PAGE_SIZE };
    if (type) filters.type = type;
    if (status) filters.status = status;
    if (dateFrom) filters.date_from = dateFrom;
    if (dateTo) filters.date_to = dateTo;
    if (search) filters.search = search;
    const payload = await walletService.transactions(filters);
    return { rows: payload.data ?? [], pagination: payload.pagination ?? null };
  };

  const { data, isLoading, error, retry } = useDashboardData<ListState>(fetcher, {
    deps: [type, status, dateFrom, dateTo, search, page],
  });

  const changeFilter = (apply: () => void) => {
    apply();
    setPage(1);
  };

  const pagination = data?.pagination ?? null;

  return (
    <PageContainer
      title="Transaction History"
      subtitle="Your complete wallet ledger in one place."
    >
      <div className="space-y-4">
        {/* Search + filters (§22–23). All server-side. */}
        <div className="space-y-2">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              changeFilter(() => setSearch(searchInput.trim()));
            }}
          >
            <input
              type="search"
              aria-label="Search transactions"
              placeholder="Search by ID, description, or reference…"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              className="w-full rounded-xl border border-surface-200 bg-surface-50 px-3.5 py-2.5 text-sm text-surface-800 placeholder:text-surface-500 focus:border-brand-500 focus:outline-none"
            />
          </form>
          <div className="flex flex-wrap gap-2">
            {TYPE_OPTIONS.map((opt) => (
              <button
                key={opt.value || 'all'}
                type="button"
                aria-pressed={type === opt.value}
                onClick={() => changeFilter(() => setType(opt.value))}
                className={cn(
                  'rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
                  type === opt.value
                    ? 'border-brand-600 bg-brand-600 text-surface-800'
                    : 'border-surface-200 bg-surface-50 text-surface-600 hover:bg-surface-100',
                )}
              >
                {opt.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <select
              aria-label="Filter by status"
              value={status}
              onChange={(e) => changeFilter(() => setStatus(e.target.value))}
              className="rounded-xl border border-surface-200 bg-surface-50 px-3 py-2 text-xs font-medium text-surface-700 focus:border-brand-500 focus:outline-none"
            >
              <option value="">All statuses</option>
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt} value={opt}>
                  {opt.charAt(0) + opt.slice(1).toLowerCase()}
                </option>
              ))}
            </select>
            <input
              type="date"
              aria-label="From date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(e) => changeFilter(() => setDateFrom(e.target.value))}
              className="rounded-xl border border-surface-200 bg-surface-50 px-3 py-2 text-xs font-medium text-surface-700 focus:border-brand-500 focus:outline-none"
            />
            <input
              type="date"
              aria-label="To date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(e) => changeFilter(() => setDateTo(e.target.value))}
              className="rounded-xl border border-surface-200 bg-surface-50 px-3 py-2 text-xs font-medium text-surface-700 focus:border-brand-500 focus:outline-none"
            />
          </div>
        </div>

        <Card>
          {isLoading ? (
            <div className="space-y-3 p-4">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-10 animate-pulse rounded-lg bg-surface-200/70" aria-hidden />
              ))}
            </div>
          ) : error ? (
            <ErrorState message={error} onRetry={retry} />
          ) : !data || data.rows.length === 0 ? (
            <div className="px-4 py-12 text-center">
              <p className="text-sm font-semibold text-surface-800">No transactions yet.</p>
              <p className="mt-1 text-xs text-surface-500">
                Your wallet activity will appear here.
              </p>
            </div>
          ) : (
            <div>
              {/* Desktop header. */}
              <div className="hidden items-center gap-4 border-b border-surface-200 px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-surface-400 md:flex">
                <span className="w-44">Type</span>
                <span className="w-36">Amount</span>
                <span className="w-24">Status</span>
                <span className="flex-1">Description</span>
                <span>Date</span>
              </div>
              <ul className="divide-y divide-surface-200">
                {data.rows.map((row) => (
                  <li key={row.transaction_id}>
                    <TransactionRow row={row} />
                  </li>
                ))}
              </ul>
            </div>
          )}

          {pagination && pagination.pages > 1 && !isLoading && !error && (
            <div className="flex items-center justify-between border-t border-surface-200 px-4 py-3">
              <button
                type="button"
                disabled={pagination.page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-xs font-semibold text-surface-700 transition-colors hover:bg-surface-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
                Prev
              </button>
              <span className="text-xs text-surface-500">
                Page {pagination.page} of {pagination.pages} · {pagination.count} total
              </span>
              <button
                type="button"
                disabled={pagination.page >= pagination.pages}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-xs font-semibold text-surface-700 transition-colors hover:bg-surface-100 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          )}
        </Card>
      </div>
    </PageContainer>
  );
}
