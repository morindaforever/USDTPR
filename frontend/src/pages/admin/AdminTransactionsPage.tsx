import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { AdminTransaction } from '@/types/admin';

type TxFilter = '' | 'DEPOSIT' | 'VIP_PURCHASE' | 'REWARD' | 'REFERRAL_COMMISSION' | 'WITHDRAWAL' | 'ADJUSTMENT';

const FILTERS: Array<{ key: TxFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: 'DEPOSIT', label: 'Deposit' },
  { key: 'VIP_PURCHASE', label: 'VIP purchase' },
  { key: 'REWARD', label: 'Reward' },
  { key: 'REFERRAL_COMMISSION', label: 'Referral commission' },
  { key: 'WITHDRAWAL', label: 'Withdrawal' },
  { key: 'ADJUSTMENT', label: 'Adjustment' },
];

/**
 * Wallet transaction viewer (§49): read-only ledger. There is deliberately
 * NO balance-editing affordance here (§50) — adjustments exist only as the
 * dedicated audited wallet-service operation if ever required.
 */
export function AdminTransactionsPage() {
  const [filter, setFilter] = useState<TxFilter>('');
  const [page, setPage] = useState(1);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.transactions({ transaction_type: filter, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load transactions.');
      return response;
    },
    [filter, page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const columns = [
    { key: 'id', header: 'Transaction', render: (row: AdminTransaction) => <span className="font-mono text-xs">{row.transaction_id}</span> },
    { key: 'user', header: 'User', render: (row: AdminTransaction) => <span className="text-xs">{row.user_id}</span> },
    { key: 'type', header: 'Type', render: (row: AdminTransaction) => <span className="text-xs">{row.transaction_type.replace(/_/g, ' ').toLowerCase()}</span> },
    { key: 'bucket', header: 'Bucket', render: (row: AdminTransaction) => <span className="text-xs text-surface-400">{row.balance_type}</span> },
    { key: 'direction', header: 'Direction', render: (row: AdminTransaction) => (
      <span className={row.direction === 'CREDIT' ? 'text-xs font-semibold text-emerald-300' : 'text-xs font-semibold text-red-300'}>
        {row.direction === 'CREDIT' ? '+' : '−'} {formatUsdt(row.amount)}
      </span>
    ) },
    { key: 'ref', header: 'Reference', render: (row: AdminTransaction) => <span className="font-mono text-[11px] text-surface-500">{row.reference_type}:{row.reference_id}</span> },
    { key: 'status', header: 'Status', render: (row: AdminTransaction) => <AdminStatusBadge status={row.status} /> },
    { key: 'date', header: 'Date', render: (row: AdminTransaction) => <span className="text-xs">{formatDateTime(row.created_at)}</span> },
  ];

  return (
    <div>
      <AdminPageHeader
        title="Wallet Transactions"
        subtitle="Read-only ledger. Balances move only through wallet-service operations — never direct edits."
      />
      <AdminTable<AdminTransaction>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No wallet transactions found"
        rowKey={(row) => row.transaction_id}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-400">{row.transaction_id}</span>
              <AdminStatusBadge status={row.status} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-surface-400">{row.user_id} · {row.balance_type}</span>
              <span className={row.direction === 'CREDIT' ? 'font-semibold tabular-nums text-emerald-300' : 'font-semibold tabular-nums text-red-300'}>
                {row.direction === 'CREDIT' ? '+' : '−'} {formatUsdt(row.amount)}
              </span>
            </div>
            <p className="text-[11px] text-surface-500">{row.transaction_type.replace(/_/g, ' ').toLowerCase()} · {formatDateTime(row.created_at)}</p>
          </div>
        )}
      />
    </div>
  );
}
