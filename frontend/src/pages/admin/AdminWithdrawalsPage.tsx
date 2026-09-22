import { useCallback, useEffect, useState } from 'react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminFilterChips, AdminPageHeader, AdminStatusBadge, AdminTable } from '@/components/admin';
import { Button, Modal } from '@/components';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { AdminWithdrawalRow } from '@/types/admin';

type WithdrawalFilter = '' | 'PENDING' | 'APPROVED' | 'PROCESSING' | 'COMPLETED' | 'REJECTED' | 'FAILED';

const FILTERS: Array<{ key: WithdrawalFilter; label: string }> = [
  { key: '', label: 'All' },
  { key: 'PENDING', label: 'Pending' },
  { key: 'APPROVED', label: 'Approved' },
  { key: 'PROCESSING', label: 'Processing' },
  { key: 'COMPLETED', label: 'Completed' },
  { key: 'REJECTED', label: 'Rejected' },
  { key: 'FAILED', label: 'Failed' },
];

/** Section 10 state machine — the only transitions the backend accepts (§26). */
const NEXT_ACTIONS: Record<AdminWithdrawalRow['status'], Array<{ key: 'approve' | 'reject' | 'processing' | 'complete' | 'fail'; label: string; danger?: boolean }>> = {
  PENDING: [
    { key: 'approve', label: 'Approve' },
    { key: 'reject', label: 'Reject', danger: true },
  ],
  // Approved = approved for manual payout → show "Payment pending" until
  // the operator marks processing/complete with a REAL transaction hash.
  APPROVED: [{ key: 'processing', label: 'Payment pending → Mark processing' }],
  PROCESSING: [
    { key: 'complete', label: 'Complete' },
    { key: 'fail', label: 'Fail', danger: true },
  ],
  COMPLETED: [],
  REJECTED: [],
  FAILED: [],
};

/** Withdrawal management (§24–29): Section 10 state machine. */
export function AdminWithdrawalsPage() {
  const [filter, setFilter] = useState<WithdrawalFilter>('PENDING');
  const [page, setPage] = useState(1);
  const [action, setAction] = useState<{ row: AdminWithdrawalRow; key: 'approve' | 'reject' | 'processing' | 'complete' | 'fail' } | null>(null);
  const [reason, setReason] = useState('');
  const [txHash, setTxHash] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<AdminWithdrawalRow | null>(null);
  const [qrUrl, setQrUrl] = useState<string | null>(null);
  const [qrError, setQrError] = useState<string | null>(null);

  // Load the user's QR image when the details modal opens.
  useEffect(() => {
    if (!expanded?.has_qr_image) {
      setQrUrl(null);
      setQrError(null);
      return;
    }
    let url: string | null = null;
    setQrError(null);
    adminService
      .withdrawalQR(expanded.withdrawal_id)
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setQrUrl(url);
      })
      .catch(() => setQrError('Unable to load the QR image.'));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [expanded?.withdrawal_id, expanded?.has_qr_image]);

  const fetcher = useCallback(
    async () => {
      const response = await adminService.withdrawals({ status: filter, page, page_size: 20 });
      if (!response.success) throw new Error(response.message || 'Unable to load withdrawals.');
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
      const payload: { reason?: string; transaction_hash?: string } = {};
      if (action.key === 'reject' || action.key === 'fail') payload.reason = reason.trim();
      if (action.key === 'complete' && txHash.trim()) payload.transaction_hash = txHash.trim();
      const envelope = await adminService.withdrawalAction(action.row.withdrawal_id, action.key, payload);
      if (!envelope.success) {
        setActionError(envelope.message || 'Action failed.');
        return;
      }
      setAction(null);
      setReason('');
      setTxHash('');
      query.retry();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  const needsReason = action?.key === 'reject' || action?.key === 'fail';
  const available = action ? NEXT_ACTIONS[action.row.status].some((a) => a.key === action.key) : false;

  const columns = [
    { key: 'id', header: 'ID', render: (row: AdminWithdrawalRow) => <span className="font-mono text-xs">{row.withdrawal_id}</span> },
    { key: 'user', header: 'User', render: (row: AdminWithdrawalRow) => <span className="text-xs">{row.user_id}</span> },
    { key: 'net', header: 'Amount', render: (row: AdminWithdrawalRow) => (
      <span className="tabular-nums">
        {formatUsdt(row.net_amount)}
        <span className="ml-1 text-[11px] text-surface-500">of {formatUsdt(row.amount)}</span>
      </span>
    ) },
    { key: 'network', header: 'Network', render: (row: AdminWithdrawalRow) => row.network },
    { key: 'status', header: 'Status', render: (row: AdminWithdrawalRow) => <AdminStatusBadge status={row.status} /> },
    { key: 'date', header: 'Created', render: (row: AdminWithdrawalRow) => <span className="text-xs">{formatDateTime(row.created_at)}</span> },
    {
      key: 'actions',
      header: 'Actions',
      render: (row: AdminWithdrawalRow) => (
        <div className="flex flex-wrap gap-1.5">
          {NEXT_ACTIONS[row.status].map((a) => (
            <Button key={a.key} size="sm" variant={a.danger ? 'danger' : 'primary'} onClick={() => { setActionError(null); setReason(''); setTxHash(''); setAction({ row, key: a.key }); }}>
              {a.label}
            </Button>
          ))}
          {NEXT_ACTIONS[row.status].length === 0 && (
            <Button size="sm" variant="ghost" onClick={() => setExpanded(row)}>Details</Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <AdminPageHeader title="Withdrawals" subtitle="Manage withdrawal requests through the Section 10 state machine." />
      <AdminTable<AdminWithdrawalRow>
        columns={columns}
        rows={rows}
        isLoading={query.isLoading}
        error={query.error}
        onRetry={query.retry}
        emptyMessage="No withdrawals found"
        rowKey={(row) => row.withdrawal_id}
        page={page}
        pageCount={Math.max(1, pagination?.pages ?? 1)}
        onPageChange={setPage}
        count={pagination?.count ?? 0}
        filters={<AdminFilterChips options={FILTERS} value={filter} onChange={(v) => { setFilter(v); setPage(1); }} />}
        renderCard={(row) => (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-surface-400">{row.withdrawal_id}</span>
              <AdminStatusBadge status={row.status} />
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-surface-400">{row.user_id} · {row.network}</span>
              <span className="font-semibold tabular-nums text-white">{formatUsdt(row.net_amount)} USDT</span>
            </div>
            <p className="truncate text-[11px] text-surface-500">→ {row.wallet_address}</p>
            {NEXT_ACTIONS[row.status].length > 0 && (
              <div className="flex flex-wrap gap-2 pt-1">
                {NEXT_ACTIONS[row.status].map((a) => (
                  <Button key={a.key} size="sm" variant={a.danger ? 'danger' : 'primary'} onClick={() => { setActionError(null); setAction({ row, key: a.key }); }}>
                    {a.label}
                  </Button>
                ))}
              </div>
            )}
          </div>
        )}
      />

      {/* Action confirm modal (§27–29, §67) */}
      <Modal
        open={action !== null}
        onClose={() => { if (!busy) setAction(null); }}
        title={action ? `Confirm: ${NEXT_ACTIONS[action.row.status].find((a) => a.key === action.key)?.label ?? action.key}` : ''}
        description="This action is audited; funds move only through the wallet ledger."
      >
        {action && (
          <div className="space-y-4">
            <dl className="space-y-1.5 rounded-xl bg-surface-200/40 p-3 text-sm">
              <div className="flex justify-between"><dt className="text-surface-400">Withdrawal</dt><dd className="font-mono text-xs">{action.row.withdrawal_id}</dd></div>
              <div className="flex justify-between"><dt className="text-surface-400">User</dt><dd>{action.row.user_id}</dd></div>
              <div className="flex justify-between"><dt className="text-surface-400">Requested</dt><dd className="tabular-nums">{formatUsdt(action.row.amount)} USDT</dd></div>
              <div className="flex justify-between"><dt className="text-surface-400">Fee / Net</dt><dd className="tabular-nums">{formatUsdt(action.row.fee_amount)} / {formatUsdt(action.row.net_amount)}</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-surface-400">Destination</dt><dd className="max-w-[12rem] truncate font-mono text-xs">{action.row.wallet_address}</dd></div>
              <div className="flex justify-between"><dt className="text-surface-400">Current status</dt><dd><AdminStatusBadge status={action.row.status} /></dd></div>
            </dl>

            {action.key === 'complete' && (
              <div>
                <label htmlFor="tx-hash" className="mb-1 block text-xs font-medium text-surface-400">
                  Transaction hash (optional — stored exactly as provided, never generated)
                </label>
                <input
                  id="tx-hash"
                  value={txHash}
                  onChange={(e) => setTxHash(e.target.value)}
                  maxLength={128}
                  className="w-full rounded-xl border border-surface-200 bg-surface-950 px-3 py-2.5 font-mono text-xs text-surface-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            )}

            {needsReason && (
              <div>
                <label htmlFor="wd-reason" className="mb-1 block text-xs font-medium text-surface-400">Reason (required)</label>
                <textarea
                  id="wd-reason"
                  value={reason}
                  rows={3}
                  maxLength={500}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full resize-none rounded-xl border border-surface-200 bg-surface-950 px-3 py-2.5 text-sm text-surface-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            )}

            {action.key === 'approve' && <p className="text-xs text-surface-400">Funds stay locked; nothing is paid out until completion.</p>}
            {(action.key === 'reject' || action.key === 'fail') && <p className="text-xs text-surface-400">The locked amount is released back to the user's withdrawable balance.</p>}

            {actionError && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{actionError}</p>}
            <div className="flex gap-2">
              <Button variant="secondary" fullWidth onClick={() => setAction(null)} disabled={busy}>Cancel</Button>
              <Button
                variant={needsReason || action.key === 'fail' ? 'danger' : 'primary'}
                fullWidth
                isLoading={busy}
                disabled={!available || (needsReason && reason.trim().length === 0)}
                onClick={() => void runAction()}
              >
                Confirm
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* Detail modal (§25) — QR viewer + payment-pending copy. */}
      <Modal open={expanded !== null} onClose={() => setExpanded(null)} title="Withdrawal details">
        {expanded && (
          <div className="space-y-4">
            {expanded.status === 'APPROVED' && (
              <div className="rounded-xl bg-amber-500/10 px-3 py-2.5 text-xs leading-relaxed text-amber-300 ring-1 ring-inset ring-amber-500/30">
                <strong>Payment pending.</strong> Approved for manual payout — send the
                real transfer externally, then mark processing and complete it with the
                actual on-chain transaction hash. Never invent a hash.
              </div>
            )}
            <dl className="space-y-2 text-sm">
              {[
                ['Withdrawal ID', expanded.withdrawal_id],
                ['User', `${expanded.user_id} · ${expanded.user_email}`],
                ['Network', expanded.network],
                ['Destination', expanded.wallet_address],
                ['Requested amount', `${formatUsdt(expanded.amount)} USDT`],
                ['Fee', `${formatUsdt(expanded.fee_amount)} USDT`],
                ['Net amount', `${formatUsdt(expanded.net_amount)} USDT`],
                ['Status', expanded.status],
                ['Created', formatDateTime(expanded.created_at)],
                ['Transaction hash', expanded.tx_hash || '— (none legitimately provided)'],
                ['Rejection reason', expanded.rejection_reason || '—'],
              ].map(([label, value]) => (
                <div key={label} className="flex justify-between gap-4">
                  <dt className="text-surface-400">{label}</dt>
                  <dd className="max-w-[60%] break-words text-right text-surface-200">{value}</dd>
                </div>
              ))}
            </dl>

            {expanded.has_qr_image && (
              <div>
                <p className="mb-1.5 text-xs font-medium text-surface-400">
                  User-uploaded QR (context only — the typed address above is authoritative)
                </p>
                {qrError ? (
                  <p className="text-xs text-red-400">{qrError}</p>
                ) : qrUrl ? (
                  <img
                    src={qrUrl}
                    alt="User-uploaded destination QR"
                    className="max-h-72 rounded-xl border border-surface-200"
                  />
                ) : (
                  <div className="h-40 w-full animate-pulse rounded-xl bg-surface-200/40" />
                )}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
