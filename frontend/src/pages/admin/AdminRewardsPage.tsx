import { useCallback, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { Button, Modal } from '@/components';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { AdminReward } from '@/types/admin';

type RewardFilter = '' | 'COMPLETED' | 'FAILED' | 'PENDING';

const FILTERS: Array<{ key: RewardFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: 'COMPLETED', label: 'Completed' },
  { key: 'FAILED', label: 'Failed' },
  { key: 'PENDING', label: 'Pending' },
];

/** Reward management (§36–39): same engine as Celery, idempotent retry. */
export function AdminRewardsPage() {
  const [filter, setFilter] = useState<RewardFilter>('');
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<AdminReward | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [confirmProcess, setConfirmProcess] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.rewards({ status: filter, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load rewards.');
      return response;
    },
    [filter, page],
  );
  const query = useDashboardData(fetcher, { deps: [filter, page] });
  const rows = query.data?.data ?? null;
  const pagination = query.data?.pagination;

  const processCycle = async () => {
    setBusy(true);
    setActionError(null);
    try {
      const envelope = await adminService.processRewards();
      if (!envelope.success) {
        setActionError(envelope.message || 'Processing failed.');
        return;
      }
      const result = envelope.data?.result as { processed?: number; credited?: number } | undefined;
      setNotice(`Cycle processed: ${result?.processed ?? 0} reward(s) evaluated, ${result?.credited ?? 0} credited.`);
      setConfirmProcess(false);
      query.retry();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Processing failed.');
    } finally {
      setBusy(false);
    }
  };

  const retry = async (reward: AdminReward) => {
    setBusy(true);
    setActionError(null);
    try {
      const envelope = await adminService.retryReward(reward.reward_id);
      if (!envelope.success) {
        setActionError(envelope.message || 'Retry failed.');
        return;
      }
      setNotice(`Reward ${reward.reward_id} retried through the idempotent reward service.`);
      setExpanded(null);
      query.retry();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Retry failed.');
    } finally {
      setBusy(false);
    }
  };

  const columns = [
    { key: 'id', header: 'Reward ID', render: (row: AdminReward) => <span className="font-mono text-xs">{row.reward_id}</span> },
    { key: 'user', header: 'User', render: (row: AdminReward) => <span className="text-xs">{row.user_id}</span> },
    { key: 'purchase', header: 'Purchase', render: (row: AdminReward) => <span className="font-mono text-xs">{row.purchase_id}</span> },
    { key: 'cycle', header: 'Cycle date', render: (row: AdminReward) => <span className="text-xs">{row.reward_date}</span> },
    { key: 'calc', header: 'Calculated', render: (row: AdminReward) => <span className="tabular-nums">{formatUsdt(row.calculated_amount)}</span> },
    { key: 'cred', header: 'Credited', render: (row: AdminReward) => <span className="tabular-nums">{formatUsdt(row.credited_amount)}</span> },
    { key: 'status', header: 'Status', render: (row: AdminReward) => <AdminStatusBadge status={row.status} /> },
    {
      key: 'actions',
      header: '',
      render: (row: AdminReward) => <Button size="sm" variant="ghost" onClick={() => setExpanded(row)}>Details</Button>,
    },
  ];

  return (
    <div>
      <AdminPageHeader
        title="Rewards"
        subtitle="VIP rewards. Processing and retry reuse the existing idempotent reward service."
        actions={
          <Button variant="secondary" onClick={() => { setActionError(null); setConfirmProcess(true); }} disabled={busy}>
            Process current cycle
          </Button>
        }
      />

      {notice && <p className="mb-3 rounded-xl bg-emerald-500/10 px-3 py-2 text-xs text-emerald-300">{notice}</p>}
      {actionError && !confirmProcess && <p className="mb-3 rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{actionError}</p>}

      <AdminTable<AdminReward>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No reward records"
        rowKey={(row) => row.reward_id}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-400">{row.reward_id}</span>
              <AdminStatusBadge status={row.status} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-surface-400">{row.user_id} · {row.reward_date}</span>
              <span className="font-semibold tabular-nums text-white">{formatUsdt(row.credited_amount)} USDT</span>
            </div>
            <Button size="sm" variant="ghost" fullWidth onClick={() => setExpanded(row)}>Details</Button>
          </div>
        )}
      />

      {/* Process confirmation (§67) */}
      <Modal open={confirmProcess} onClose={() => { if (!busy) setConfirmProcess(false); }} title="Process current cycle" description="Runs the same reward service as Celery Beat — idempotent, safe to re-run.">
        <div className="space-y-4">
          <p className="text-sm text-surface-300">
            Existing rewards, target caps, and completed purchases are respected. No wallet can be credited twice.
          </p>
          {actionError && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{actionError}</p>}
          <div className="flex gap-2">
            <Button variant="secondary" fullWidth onClick={() => setConfirmProcess(false)} disabled={busy}>Cancel</Button>
            <Button fullWidth isLoading={busy} onClick={() => void processCycle()}>Process</Button>
          </div>
        </div>
      </Modal>

      {/* Reward detail (§37) */}
      <Modal open={expanded !== null} onClose={() => setExpanded(null)} title="Reward detail">
        {expanded && (
          <div className="space-y-4">
            <dl className="space-y-2 text-sm">
              {[
                ['Reward ID', expanded.reward_id],
                ['User', `${expanded.user_id} · ${expanded.user_email}`],
                ['Purchase', expanded.purchase_id],
                ['Cycle date', expanded.reward_date],
                ['Calculated amount', `${formatUsdt(expanded.calculated_amount)} USDT`],
                ['Credited amount', `${formatUsdt(expanded.credited_amount)} USDT`],
                ['Status', expanded.status],
                ['Created', formatDateTime(expanded.created_at)],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt className="text-surface-400">{label}</dt>
                  <dd className="max-w-[60%] break-words text-right text-surface-200">{value}</dd>
                </div>
              ))}
            </dl>
            {expanded.error_info && (
              <div>
                <p className="mb-1 text-xs font-medium text-surface-400">Error information (staff only)</p>
                <p className="rounded-xl bg-white/5 p-3 text-xs text-surface-300">{expanded.error_info}</p>
              </div>
            )}
            {expanded.status === 'FAILED' && (
              <Button variant="secondary" fullWidth isLoading={busy} onClick={() => void retry(expanded)}>
                Retry through reward service
              </Button>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
