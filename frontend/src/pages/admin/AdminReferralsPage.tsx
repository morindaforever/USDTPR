import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { formatDateTime } from '@/utils/format';
import type { AdminReferralRow } from '@/types/admin';

type ReferralFilter = '' | '1' | '2' | '3' | 'ACTIVE' | 'INACTIVE' | 'BLOCKED';

const FILTERS: Array<{ key: ReferralFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: '1', label: 'Level 1' },
  { key: '2', label: 'Level 2' },
  { key: '3', label: 'Level 3' },
  { key: 'ACTIVE', label: 'Active' },
  { key: 'INACTIVE', label: 'Inactive' },
  { key: 'BLOCKED', label: 'Blocked' },
];

/** Referral relationship management (§40–41). Read-only + filters. */
export function AdminReferralsPage() {
  const [filter, setFilter] = useState<ReferralFilter>('');
  const [page, setPage] = useState(1);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.referrals({ level: ['1', '2', '3'].includes(filter) ? filter : undefined, status: ['ACTIVE', 'INACTIVE', 'BLOCKED'].includes(filter) ? filter : undefined, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load referrals.');
      return response;
    },
    [filter, page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const columns = [
    { key: 'id', header: 'ID', render: (row: AdminReferralRow) => <span className="font-mono text-xs">#{row.id}</span> },
    { key: 'referrer', header: 'Referrer', render: (row: AdminReferralRow) => (
      <span className="text-xs">{row.referrer_id}<span className="ml-1 text-surface-500">{row.referrer_email}</span></span>
    ) },
    { key: 'referred', header: 'Referred user', render: (row: AdminReferralRow) => (
      <span className="text-xs">{row.referred_id}<span className="ml-1 text-surface-500">{row.referred_email}</span></span>
    ) },
    { key: 'status', header: 'Status', render: (row: AdminReferralRow) => <AdminStatusBadge status={row.status} /> },
    { key: 'date', header: 'Created', render: (row: AdminReferralRow) => <span className="text-xs">{formatDateTime(row.created_at)}</span> },
  ];

  return (
    <div>
      <AdminPageHeader title="Referrals" subtitle="Referral relationships. Rate snapshots live on each commission." />
      <AdminTable<AdminReferralRow>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No referral relationships found"
        rowKey={(row) => String(row.id)}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-400">#{row.id}</span>
              <AdminStatusBadge status={row.status} />
            </div>
            <p className="text-xs text-surface-300">{row.referrer_id} → {row.referred_id}</p>
            <p className="text-[11px] text-surface-500">{formatDateTime(row.created_at)}</p>
          </div>
        )}
      />
    </div>
  );
}
