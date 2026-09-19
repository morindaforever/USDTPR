import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminTable } from '@/components/admin';
import { formatDateTime } from '@/utils/format';
import type { AdminAuditLog } from '@/types/admin';

type AuditFilter = 'admin' | 'user';

const FILTERS: Array<{ key: AuditFilter; label: string }> = [
  { key: 'admin', label: 'Admin actions' },
  { key: 'user', label: 'User activity' },
];

/** Audit log viewer (§54–55): strictly read-only, append-only backend. */
export function AdminAuditLogsPage() {
  const [filter, setFilter] = useState<AuditFilter>('admin');
  const [page, setPage] = useState(1);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.auditLogs({ actor: filter, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load audit logs.');
      return response;
    },
    [filter, page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const columns = [
    { key: 'date', header: 'Timestamp', render: (row: AdminAuditLog) => <span className="whitespace-nowrap text-xs">{formatDateTime(row.created_at)}</span> },
    { key: 'actor', header: 'Actor', render: (row: AdminAuditLog) => (
      <span className="text-xs">{row.actor_id ?? 'system'}{row.actor_email && <span className="ml-1 text-surface-500">{row.actor_email}</span>}</span>
    ) },
    { key: 'action', header: 'Action', render: (row: AdminAuditLog) => <span className="font-mono text-xs text-surface-200">{row.action}</span> },
    { key: 'target', header: 'Object', render: (row: AdminAuditLog) => (
      <span className="font-mono text-[11px] text-surface-500">{row.target_type}:{row.target_id}</span>
    ) },
    { key: 'ip', header: 'IP', render: (row: AdminAuditLog) => <span className="font-mono text-[11px] text-surface-500">{row.ip_address ?? '—'}</span> },
    { key: 'desc', header: 'Description', render: (row: AdminAuditLog) => <span className="line-clamp-1 max-w-[18rem] text-xs text-surface-400">{row.description}</span> },
  ];

  return (
    <div>
      <AdminPageHeader
        title="Audit Logs"
        subtitle="Append-only record of sensitive actions. Logs cannot be edited or deleted from this panel."
      />
      <AdminTable<AdminAuditLog>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No audit entries found"
        rowKey={(row) => String(row.id)}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-200">{row.action}</span>
              <span className="text-[11px] text-surface-500">{formatDateTime(row.created_at)}</span>
            </div>
            <p className="text-xs text-surface-400">{row.actor_id ?? 'system'} → {row.target_type}:{row.target_id}</p>
            {row.description && <p className="line-clamp-2 text-[11px] text-surface-500">{row.description}</p>}
          </div>
        )}
      />
    </div>
  );
}
