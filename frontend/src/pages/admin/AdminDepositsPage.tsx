import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { Button, Modal } from '@/components';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { AdminDepositRow } from '@/types/admin';

type DepositFilter = '' | 'PENDING' | 'APPROVED' | 'REJECTED';

const FILTERS: Array<{ key: DepositFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: 'PENDING', label: 'Pending' },
  { key: 'APPROVED', label: 'Approved' },
  { key: 'REJECTED', label: 'Rejected' },
];

/** Deposit management (§18–21): reuse of the Section 6 approval workflow. */
export function AdminDepositsPage() {
  const [filter, setFilter] = useState<DepositFilter>('PENDING');
  const [page, setPage] = useState(1);
  const [action, setAction] = useState<{ row: AdminDepositRow; kind: 'approve' | 'reject' } | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<AdminDepositRow | null>(null);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.deposits({ status: filter, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load deposits.');
      return response;
    },
    [filter, page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const runAction = async () => {
    if (!action || busy) return;
    setBusy(true);
    setActionError(null);
    try {
      const envelope = await adminService.depositAction(action.row.deposit_id, action.kind, reason.trim());
      if (!envelope.success) {
        setActionError(envelope.message || 'Action failed.');
        return;
      }
      setAction(null);
      setReason('');
      query.retry();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    { key: 'id', header: 'Deposit ID', render: (row: AdminDepositRow) => <span className="font-mono text-xs">{row.deposit_id}</span> },
    { key: 'user', header: 'User', render: (row: AdminDepositRow) => <span className="text-xs">{row.user_id}</span> },
    { key: 'network', header: 'Network', render: (row: AdminDepositRow) => row.network },
    { key: 'amount', header: 'Amount', render: (row: AdminDepositRow) => <span className="tabular-nums">{formatUsdt(row.amount)}</span> },
    { key: 'status', header: 'Status', render: (row: AdminDepositRow) => <AdminStatusBadge status={row.status} /> },
    { key: 'date', header: 'Submitted', render: (row: AdminDepositRow) => <span className="text-xs">{formatDateTime(row.created_at)}</span> },
    {
      key: 'actions',
      header: 'Actions',
      render: (row: AdminDepositRow) =>
        row.status === 'PENDING' ? (
          <div className="flex gap-1.5">
            <Button size="sm" onClick={() => { setActionError(null); setAction({ row, kind: 'approve' }); }}>
              Approve
            </Button>
            <Button size="sm" variant="danger" onClick={() => { setActionError(null); setAction({ row, kind: 'reject' }); }}>
              Reject
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="ghost" onClick={() => setExpanded(row)}>
            Details
          </Button>
        ),
    },
  ];

  return (
    <div>
      <AdminPageHeader title="Deposits" subtitle="Review and approve user deposit requests." />
      <AdminTable<AdminDepositRow>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No deposits found"
        rowKey={(row) => row.deposit_id}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-400">{row.deposit_id}</span>
              <AdminStatusBadge status={row.status} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-surface-400">{row.user_id} · {row.network}</span>
              <span className="font-semibold tabular-nums text-white">{formatUsdt(row.amount)} USDT</span>
            </div>
            {row.status === 'PENDING' && (
              <div className="flex gap-2 pt-1">
                <Button size="sm" fullWidth onClick={() => { setActionError(null); setAction({ row, kind: 'approve' }); }}>Approve</Button>
                <Button size="sm" variant="danger" fullWidth onClick={() => { setActionError(null); setAction({ row, kind: 'reject' }); }}>Reject</Button>
              </div>
            )}
          </div>
        )}
      />

      {/* Confirm modal (§20–21, §67) */}
      <Modal
        open={action !== null}
        onClose={() => { if (!busy) setAction(null); }}
        title={action?.kind === 'approve' ? 'Approve deposit' : 'Reject deposit'}
        description="This action is audited and notifies the user."
      >
        {action && (
          <div className="space-y-4">
            <dl className="space-y-1.5 rounded-xl bg-white/5 p-3 text-sm">
              <div className="flex justify-between"><dt className="text-surface-400">User</dt><dd>{action.row.user_id}</dd></div>
              <div className="flex justify-between"><dt className="text-surface-400">Amount</dt><dd className="tabular-nums">{formatUsdt(action.row.amount)} USDT</dd></div>
              <div className="flex justify-between"><dt className="text-surface-400">Network</dt><dd>{action.row.network}</dd></div>
              <div className="flex justify-between"><dt className="text-surface-400">Tx hash</dt><dd className="max-w-[10rem] truncate font-mono text-xs">{action.row.tx_hash || '—'}</dd></div>
            </dl>
            {action.kind === 'reject' && (
              <div>
                <label htmlFor="reject-reason" className="mb-1 block text-xs font-medium text-surface-400">Reason (required)</label>
                <textarea
                  id="reject-reason"
                  value={reason}
                  rows={3}
                  maxLength={500}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full resize-none rounded-xl border border-white/10 bg-surface-950 px-3 py-2.5 text-sm text-surface-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            )}
            {action.kind === 'approve' && (
              <p className="text-xs text-surface-400">
                Approval credits the user's deposit balance exactly once through the wallet ledger.
              </p>
            )}
            {actionError && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{actionError}</p>}
            <div className="flex gap-2">
              <Button variant="secondary" fullWidth onClick={() => setAction(null)} disabled={busy}>Cancel</Button>
              <Button
                variant={action.kind === 'approve' ? 'primary' : 'danger'}
                fullWidth
                isLoading={busy}
                disabled={action.kind === 'reject' && reason.trim().length === 0}
                onClick={() => void runAction()}
              >
                Confirm {action.kind === 'approve' ? 'Approve' : 'Reject'}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Detail modal (§19) */}
      <Modal open={expanded !== null} onClose={() => setExpanded(null)} title="Deposit details">
        {expanded && (
          <dl className="space-y-2 text-sm">
            {[
              ['Deposit ID', expanded.deposit_id],
              ['User', expanded.user_id],
              ['Network', expanded.network],
              ['Amount', `${formatUsdt(expanded.amount)} USDT`],
              ['Tx / order ID', expanded.tx_hash || expanded.order_id || '—'],
              ['Status', expanded.status],
              ['Submitted', formatDateTime(expanded.created_at)],
              ['Reviewed', expanded.reviewed_at ? formatDateTime(expanded.reviewed_at) : '—'],
              ['Reviewer', expanded.reviewer_email || '—'],
              ['Admin note', expanded.admin_note || '—'],
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
