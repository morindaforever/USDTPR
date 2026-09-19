import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { Button } from '@/components';
import { formatDateTime } from '@/utils/format';
import type { AdminSupportRow } from '@/types/admin';

type SupportFilter = '' | 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';

const FILTERS: Array<{ key: SupportFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: 'OPEN', label: 'Open' },
  { key: 'IN_PROGRESS', label: 'In progress' },
  { key: 'RESOLVED', label: 'Resolved' },
  { key: 'CLOSED', label: 'Closed' },
];

/** Support management (§44–48): full staff interface for conversations. */
export function AdminSupportPage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<SupportFilter>('OPEN');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.support({ status: filter, search, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load conversations.');
      return response;
    },
    [filter, search, page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, search, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const columns = [
    { key: 'id', header: 'Conversation', render: (row: AdminSupportRow) => <span className="font-mono text-xs">{row.conversation_id}</span> },
    { key: 'user', header: 'User', render: (row: AdminSupportRow) => <span className="text-xs">{row.user_id}<span className="ml-1 text-surface-500">{row.user_email}</span></span> },
    { key: 'subject', header: 'Subject', render: (row: AdminSupportRow) => <span className="text-surface-200">{row.subject}</span> },
    { key: 'status', header: 'Status', render: (row: AdminSupportRow) => <AdminStatusBadge status={row.status} /> },
    { key: 'preview', header: 'Last message', render: (row: AdminSupportRow) => <span className="line-clamp-1 max-w-[14rem] text-xs text-surface-400">{row.last_message_preview || '—'}</span> },
    { key: 'updated', header: 'Updated', render: (row: AdminSupportRow) => <span className="text-xs">{formatDateTime(row.updated_at)}</span> },
    {
      key: 'open',
      header: '',
      render: (row: AdminSupportRow) => (
        <Button size="sm" variant="secondary" onClick={() => navigate(`/admin/support/${row.conversation_id}`)}>Open</Button>
      ),
    },
  ];

  return (
    <div>
      <AdminPageHeader title="Support" subtitle="User conversations. Replies notify the user and are audited." />
      <AdminTable<AdminSupportRow>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No support conversations"
        rowKey={(row) => row.conversation_id}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        searchValue={search}
        onSearchChange={(value) => { setSearch(value); setPage(1); }}
        searchPlaceholder="Search ID, user, subject…"
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <button
            type="button"
            className="w-full space-y-2 text-left"
            onClick={() => navigate(`/admin/support/${row.conversation_id}`)}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-400">{row.conversation_id}</span>
              <AdminStatusBadge status={row.status} />
            </div>
            <p className="text-sm font-medium text-surface-200">{row.subject}</p>
            <p className="text-[11px] text-surface-500">{row.user_id} · {formatDateTime(row.updated_at)}</p>
          </button>
        )}
      />
    </div>
  );
}
