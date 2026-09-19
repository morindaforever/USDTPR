import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { Button, Input, Modal } from '@/components';
import { formatDateTime } from '@/utils/format';
import type { AdminNotification } from '@/types/admin';

type NotificationFilter = '' | 'all_active' | 'vip' | 'depositors' | 'withdrawers';

const AUDIENCES: Array<{ key: NotificationFilter; label: string }> = [
  { key: 'all_active', label: 'All active users' },
  { key: 'vip', label: 'VIP users' },
  { key: 'depositors', label: 'Users with deposits' },
  { key: 'withdrawers', label: 'Users with withdrawals' },
];

/** Notification management (§52–53): list + announcement broadcast. */
export function AdminNotificationsPage() {
  const [filter, setFilter] = useState<NotificationFilter>('all_active');
  const [page, setPage] = useState(1);
  const [broadcast, setBroadcast] = useState(false);
  const [title, setTitle] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.notifications({ page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load notifications.');
      return response;
    },
    [page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const sendBroadcast = async () => {
    setBusy(true);
    setError(null);
    try {
      const envelope = await adminService.broadcast({ title: title.trim(), message: message.trim(), audience: filter });
      if (!envelope.success) {
        setError(envelope.message || 'Broadcast failed.');
        return;
      }
      setNotice(`Announcement delivered to ${envelope.data?.delivered ?? 0} user(s).`);
      setBroadcast(false);
      setConfirmOpen(false);
      setTitle('');
      setMessage('');
      query.retry();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Broadcast failed.');
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    { key: 'id', header: 'ID', render: (row: AdminNotification) => <span className="font-mono text-xs">#{row.id}</span> },
    { key: 'user', header: 'User', render: (row: AdminNotification) => <span className="text-xs">{row.user_id}</span> },
    { key: 'type', header: 'Type', render: (row: AdminNotification) => <span className="text-xs">{row.notification_type}</span> },
    { key: 'title', header: 'Title', render: (row: AdminNotification) => <span className="text-surface-200">{row.title}</span> },
    { key: 'message', header: 'Message', render: (row: AdminNotification) => <span className="line-clamp-1 max-w-[16rem] text-xs text-surface-400">{row.message}</span> },
    { key: 'read', header: 'Read', render: (row: AdminNotification) => (
      <AdminStatusBadge status={row.is_read ? 'COMPLETED' : 'PENDING'} />
    ) },
    { key: 'date', header: 'Sent', render: (row: AdminNotification) => <span className="text-xs">{formatDateTime(row.created_at)}</span> },
  ];

  return (
    <div>
      <AdminPageHeader
        title="Notifications"
        subtitle="System notification log and announcement broadcasting."
        actions={<Button variant="secondary" onClick={() => { setError(null); setBroadcast(true); }}>New announcement</Button>}
      />

      {notice && <p className="mb-3 rounded-xl bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">{notice}</p>}

      <AdminTable<AdminNotification>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No notifications found"
        rowKey={(row) => String(row.id)}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        renderCard={(row) => (
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs text-surface-400">{row.user_id} · {row.notification_type}</span>
              <AdminStatusBadge status={row.is_read ? 'COMPLETED' : 'PENDING'} />
            </div>
            <p className="text-sm font-medium text-surface-200">{row.title}</p>
            <p className="line-clamp-2 text-xs text-surface-400">{row.message}</p>
            <p className="text-[11px] text-surface-500">{formatDateTime(row.created_at)}</p>
          </div>
        )}
      />

      {/* Compose modal */}
      <Modal open={broadcast && !confirmOpen} onClose={() => { if (!busy) setBroadcast(false); }} title="New announcement" description="Plain text only — HTML is never rendered.">
        <div className="space-y-3">
          <Input label="Title" value={title} maxLength={120} onChange={(e) => setTitle(e.target.value)} />
          <div>
            <label htmlFor="broadcast-message" className="mb-1 block text-xs font-medium text-surface-400">Message</label>
            <textarea
              id="broadcast-message"
              value={message}
              rows={4}
              maxLength={1000}
              onChange={(e) => setMessage(e.target.value)}
              className="w-full resize-none rounded-xl border border-white/10 bg-surface-950 px-3 py-2.5 text-sm text-surface-100 focus:border-brand-500 focus:outline-none"
            />
          </div>
          <div>
            <p className="mb-1.5 text-xs font-medium text-surface-400">Target audience (backend determines membership)</p>
            <AdminFilterChips options={AUDIENCES} value={filter} onChange={setFilter} />
          </div>
          {error && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</p>}
          <div className="flex gap-2">
            <Button variant="secondary" fullWidth onClick={() => setBroadcast(false)} disabled={busy}>Cancel</Button>
            <Button fullWidth disabled={title.trim().length === 0 || message.trim().length === 0} onClick={() => setConfirmOpen(true)}>
              Review & send
            </Button>
          </div>
        </div>
      </Modal>

      {/* Confirmation (§52, §67) */}
      <Modal open={confirmOpen} onClose={() => { if (!busy) setConfirmOpen(false); }} title="Confirm announcement">
        <div className="space-y-4">
          <dl className="space-y-1.5 rounded-xl bg-white/5 p-3 text-sm">
            <div className="flex justify-between"><dt className="text-surface-400">Audience</dt><dd>{AUDIENCES.find((a) => a.key === filter)?.label}</dd></div>
            <div className="flex justify-between"><dt className="text-surface-400">Title</dt><dd className="max-w-[60%] truncate">{title}</dd></div>
          </dl>
          {error && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</p>}
          <div className="flex gap-2">
            <Button variant="secondary" fullWidth onClick={() => setConfirmOpen(false)} disabled={busy}>Back</Button>
            <Button fullWidth isLoading={busy} onClick={() => void sendBroadcast()}>Send now</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
