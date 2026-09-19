import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { Button, Modal } from '@/components';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { AdminVipPurchase } from '@/types/admin';

type PurchaseFilter = '' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED' | 'FAILED';

const FILTERS: Array<{ key: PurchaseFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: 'ACTIVE', label: 'Active' },
  { key: 'COMPLETED', label: 'Completed' },
  { key: 'CANCELLED', label: 'Cancelled' },
  { key: 'FAILED', label: 'Failed' },
];

/** VIP purchase management (§34–35): read-only snapshot view, no edits. */
export function AdminVipPurchasesPage() {
  const [filter, setFilter] = useState<PurchaseFilter>('ACTIVE');
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<AdminVipPurchase | null>(null);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.vipPurchases({ status: filter, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load purchases.');
      return response;
    },
    [filter, page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const progress = (row: AdminVipPurchase) => {
    const target = Number(row.target_amount);
    if (!Number.isFinite(target) || target <= 0) return 0;
    return Math.min(100, Math.round((Number(row.rewarded_amount) / target) * 100));
  };

  const columns = [
    { key: 'id', header: 'Purchase', render: (row: AdminVipPurchase) => <span className="font-mono text-xs">{row.purchase_id}</span> },
    { key: 'user', header: 'User', render: (row: AdminVipPurchase) => <span className="text-xs">{row.user_id}</span> },
    { key: 'plan', header: 'Plan (snapshot)', render: (row: AdminVipPurchase) => row.plan_name_snapshot },
    { key: 'inv', header: 'Investment', render: (row: AdminVipPurchase) => <span className="tabular-nums">{formatUsdt(row.investment_amount)}</span> },
    { key: 'prog', header: 'Progress', render: (row: AdminVipPurchase) => (
      <div className="min-w-[7rem]">
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-brand-500" style={{ width: `${progress(row)}%` }} />
        </div>
        <span className="text-[11px] text-surface-500">{formatUsdt(row.rewarded_amount)} / {formatUsdt(row.target_amount)}</span>
      </div>
    ) },
    { key: 'status', header: 'Status', render: (row: AdminVipPurchase) => <AdminStatusBadge status={row.status} /> },
    { key: 'date', header: 'Started', render: (row: AdminVipPurchase) => <span className="text-xs">{row.started_at ? formatDateTime(row.started_at) : '—'}</span> },
    {
      key: 'actions',
      header: '',
      render: (row: AdminVipPurchase) => <Button size="sm" variant="ghost" onClick={() => setExpanded(row)}>Details</Button>,
    },
  ];

  return (
    <div>
      <AdminPageHeader title="VIP Purchases" subtitle="Snapshot terms are immutable — plans may change, purchases do not." />
      <AdminTable<AdminVipPurchase>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No VIP purchases found"
        rowKey={(row) => row.purchase_id}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-400">{row.purchase_id}</span>
              <AdminStatusBadge status={row.status} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-surface-400">{row.user_id} · {row.plan_name_snapshot}</span>
              <span className="font-semibold tabular-nums text-white">{progress(row)}%</span>
            </div>
            <p className="text-[11px] text-surface-500">
              {formatUsdt(row.rewarded_amount)} / {formatUsdt(row.target_amount)} USDT rewarded · {row.daily_rate_snapshot}% daily
            </p>
            <Button size="sm" variant="ghost" fullWidth onClick={() => setExpanded(row)}>Details</Button>
          </div>
        )}
      />

      <Modal open={expanded !== null} onClose={() => setExpanded(null)} title="Purchase detail (read-only)">
        {expanded && (
          <dl className="space-y-2 text-sm">
            {[
              ['Purchase ID', expanded.purchase_id],
              ['User', `${expanded.user_id} · ${expanded.user_email}`],
              ['Plan snapshot', expanded.plan_name_snapshot],
              ['Investment', `${formatUsdt(expanded.investment_amount)} USDT`],
              ['Target', `${formatUsdt(expanded.target_amount)} USDT`],
              ['Daily rate (snapshot)', `${expanded.daily_rate_snapshot}%`],
              ['Rewarded so far', `${formatUsdt(expanded.rewarded_amount)} USDT`],
              ['Remaining', `${formatUsdt(expanded.remaining_amount)} USDT`],
              ['Status', expanded.status],
              ['Start date', expanded.started_at ? formatDateTime(expanded.started_at) : '—'],
              ['Created', formatDateTime(expanded.created_at)],
            ].map(([label, value]) => (
              <div key={label} className="flex justify-between gap-4">
                <dt className="text-surface-400">{label}</dt>
                <dd className="max-w-[60%] break-words text-right text-surface-200">{value}</dd>
              </div>
            ))}
          </dl>
        )}
      </Modal>
    </div>
  );
}
