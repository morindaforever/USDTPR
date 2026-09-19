import { useCallback, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { formatDate } from '@/utils/format';
import type { AdminUserRow } from '@/types/admin';

type StatusFilter = '' | 'ACTIVE' | 'SUSPENDED' | 'BANNED';

const STATUS_OPTIONS: Array<{ key: StatusFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: 'ACTIVE', label: 'Active' },
  { key: 'SUSPENDED', label: 'Suspended' },
  { key: 'BANNED', label: 'Banned' },
];

/** User management (§10–13): server-side search, filters, pagination. */
export function AdminUsersPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState<StatusFilter>('');
  const [page, setPage] = useState(1);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.users({ search, status, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load users.');
      return response;
    },
    [search, status, page],
  );

  const query = useDashboardData(fetcher, { deps: [search, status, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;
  const pageCount = Math.max(1, pagination?.pages ?? 1);

  const columns = [
    {
      key: 'user_id',
      header: 'User ID',
      render: (row: AdminUserRow) => (
        <button
          type="button"
          onClick={() => navigate(`/admin/users/${row.user_id}`)}
          className="font-mono text-xs font-semibold text-brand-300 hover:text-brand-200"
        >
          {row.user_id}
        </button>
      ),
    },
    { key: 'name', header: 'Name', render: (row: AdminUserRow) => row.full_name || '—' },
    { key: 'email', header: 'Email', render: (row: AdminUserRow) => <span className="text-xs">{row.email}</span> },
    { key: 'phone', header: 'Phone', render: (row: AdminUserRow) => <span className="tabular-nums text-xs">{row.phone}</span> },
    { key: 'status', header: 'Status', render: (row: AdminUserRow) => <AdminStatusBadge status={row.account_status} /> },
    { key: 'staff', header: 'Staff', render: (row: AdminUserRow) => (row.is_staff ? 'Yes' : '—') },
    { key: 'created', header: 'Registered', render: (row: AdminUserRow) => <span className="text-xs">{formatDate(row.created_at)}</span> },
  ];

  return (
    <div>
      <AdminPageHeader title="Users" subtitle="Search, review, and manage platform accounts." />
      <AdminTable<AdminUserRow>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No users found"
        rowKey={(row) => row.user_id}
        page={page}
        pageCount={pageCount}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        searchValue={search}
        onSearchChange={(value) => {
          setSearch(value);
          setPage(1);
        }}
        searchPlaceholder="Search ID, name, email, phone…"
        filters={<AdminFilterChips options={STATUS_OPTIONS} value={status} onChange={(v) => { setStatus(v); setPage(1); }} />}
        renderCard={(row) => (
          <button
            type="button"
            onClick={() => navigate(`/admin/users/${row.user_id}`)}
            className="flex w-full items-center justify-between gap-2 text-left"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-surface-200">{row.full_name || row.email}</p>
              <p className="font-mono text-[11px] text-surface-500">{row.user_id}</p>
            </div>
            <AdminStatusBadge status={row.account_status} />
          </button>
        )}
      />
    </div>
  );
}
