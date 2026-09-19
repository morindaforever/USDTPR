import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { AdminCommissionRow } from '@/types/admin';

type CommissionFilter = '' | 'PENDING' | 'CREDITED' | 'FAILED' | 'REVERSED';

const FILTERS: Array<{ key: CommissionFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: 'PENDING', label: 'Pending' },
  { key: 'CREDITED', label: 'Credited' },
  { key: 'FAILED', label: 'Failed' },
  { key: 'REVERSED', label: 'Reversed' },
];

/** Commission management (§42–43): read-only, snapshots immutable. */
export function AdminCommissionsPage() {
  const [filter, setFilter] = useState<CommissionFilter>('CREDITED');
  const [page, setPage] = useState(1);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.commissions({ status: filter, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load commissions.');
      return response;
    },
    [filter, page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const columns = [
    { key: 'id', header: 'Commission', render: (row: AdminCommissionRow) => <span className="font-mono text-xs">{row.commission_id}</span> },
    { key: 'beneficiary', header: 'Beneficiary', render: (row: AdminCommissionRow) => <span className="text-xs">{row.beneficiary_id}</span> },
    { key: 'source', header: 'Source user', render: (row: AdminCommissionRow) => <span className="text-xs">{row.source_user_id}</span> },
    { key: 'level', header: 'Level', render: (row: AdminCommissionRow) => <span>L{row.level}</span> },
    { key: 'rate', header: 'Rate (snapshot)', render: (row: AdminCommissionRow) => <span className="tabular-nums text-xs">{row.commission_rate}%</span> },
    { key: 'base', header: 'Source reward', render: (row: AdminCommissionRow) => <span className="tabular-nums text-xs">{formatUsdt(row.source_reward_amount)}</span> },
    { key: 'amount', header: 'Commission', render: (row: AdminCommissionRow) => <span className="font-semibold tabular-nums text-white">{formatUsdt(row.commission_amount)}</span> },
    { key: 'status', header: 'Status', render: (row: AdminCommissionRow) => <AdminStatusBadge status={row.status} /> },
    { key: 'date', header: 'Date', render: (row: AdminCommissionRow) => <span className="text-xs">{formatDateTime(row.created_at)}</span> },
  ];

  return (
    <div>
      <AdminPageHeader title="Commissions" subtitle="Referral commissions. Historical rates and amounts are snapshots and never change." />
      <AdminTable<AdminCommissionRow>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No commission records"
        rowKey={(row) => row.commission_id}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-400">{row.commission_id}</span>
              <AdminStatusBadge status={row.status} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-surface-400">L{row.level} · {row.beneficiary_id}</span>
              <span className="font-semibold tabular-nums text-white">{formatUsdt(row.commission_amount)} USDT</span>
            </div>
            <p className="text-[11px] text-surface-500">from {row.source_user_id}'s reward · rate {row.commission_rate}%</p>
          </div>
        )}
      />
    </div>
  );
}
