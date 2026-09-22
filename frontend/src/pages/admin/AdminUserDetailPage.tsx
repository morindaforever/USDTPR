import { useCallback, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { adminService } from '@/services/adminService';
import { Skeleton, useDashboardData } from '@/hooks';
import { AdminPageHeader, AdminStatusBadge } from '@/components/admin';
import { Button, Modal } from '@/components';
import { formatDate, formatDateTime, formatUsdt } from '@/utils/format';
import type { AdminUserDetail } from '@/types/admin';

type HistoryTab = 'deposits' | 'withdrawals' | 'vip' | 'rewards' | 'commissions' | 'support' | 'logins' | 'audit';

const TABS: Array<{ key: HistoryTab; label: string }> = [
  { key: 'deposits', label: 'Deposits' },
  { key: 'withdrawals', label: 'Withdrawals' },
  { key: 'vip', label: 'VIP' },
  { key: 'rewards', label: 'Rewards' },
  { key: 'commissions', label: 'Commissions' },
  { key: 'support', label: 'Support' },
  { key: 'logins', label: 'Logins' },
  { key: 'audit', label: 'Audit' },
];

interface StatusAction {
  action: 'activate' | 'suspend' | 'ban';
  label: string;
  verb: string;
  needsReason: boolean;
  danger?: boolean;
}

const ACTIONS: StatusAction[] = [
  { action: 'activate', label: 'Activate', verb: 'activate', needsReason: false },
  { action: 'suspend', label: 'Suspend', verb: 'suspend', needsReason: true, danger: true },
  { action: 'ban', label: 'Ban', verb: 'ban', needsReason: true, danger: true },
];

/**
 * User detail (§14–16). Read-only profile + wallet; status changes go
 * through the dedicated audited endpoint — never a generic field edit.
 */
export function AdminUserDetailPage() {
  const { userId } = useParams<{ userId: string }>();
  const navigate = useNavigate();

  const [tab, setTab] = useState<HistoryTab>('deposits');
  const [confirmAction, setConfirmAction] = useState<StatusAction | null>(null);
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const userQuery = useDashboardData<AdminUserDetail>(
    useCallback(async () => {
      const envelope = await adminService.user(userId ?? '');
      if (!envelope.success || !envelope.data) throw new Error(envelope.message || 'User not found.');
      return envelope.data;
    }, [userId]),
  );

  const historyQuery = useDashboardData<unknown[]>(
    useCallback(async () => {
      const envelope = await adminService.userHistory(userId ?? '', tab);
      return envelope.data?.results ?? [];
    }, [userId, tab]),
    { enabled: Boolean(userId) },
  );

  const runAction = async () => {
    if (!confirmAction || !userId || busy) return;
    setBusy(true);
    setActionError(null);
    try {
      const envelope = await adminService.userStatus(userId, confirmAction.action, reason.trim());
      if (!envelope.success) {
        setActionError(envelope.message || 'Action failed.');
        return;
      }
      setConfirmAction(null);
      setReason('');
      userQuery.retry();
      historyQuery.retry();
    } catch (err: unknown) {
      setActionError(err instanceof Error ? err.message : 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  const user = userQuery.data;

  return (
    <div>
      <AdminPageHeader
        title={user ? user.full_name || user.email : 'User'}
        subtitle={user?.user_id}
        actions={
          <Button variant="ghost" size="sm" onClick={() => navigate('/admin/users')}>
            ← All users
          </Button>
        }
      />

      {userQuery.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-40 w-full rounded-2xl bg-surface-200/40" />
          <Skeleton className="h-64 w-full rounded-2xl bg-surface-200/40" />
        </div>
      ) : userQuery.error || !user ? (
        <div className="rounded-2xl border border-surface-200 bg-surface-50 p-6 text-center text-sm text-surface-300">
          {userQuery.error || 'User not found.'}
        </div>
      ) : (
        <div className="space-y-5">
          {/* Account (§14) */}
          <section className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-white">Account</h2>
                <dl className="mt-2 grid gap-x-8 gap-y-1.5 text-sm sm:grid-cols-2">
                  {[
                    ['Email', user.email],
                    ['Phone', user.phone],
                    ['Referral code', user.referral_code],
                    ['Registered', formatDate(user.created_at)],
                    ['Last login', user.last_login ? formatDateTime(user.last_login) : 'Never'],
                    ['Direct referrals', String(user.direct_referrals_count)],
                  ].map(([label, value]) => (
                    <div key={label} className="flex justify-between gap-4 sm:justify-start">
                      <dt className="text-surface-500">{label}</dt>
                      <dd className="font-medium text-surface-200">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div className="flex flex-col items-end gap-2">
                <AdminStatusBadge status={user.account_status} />
                <div className="flex gap-1.5">
                  {ACTIONS.map((item) => (
                    <Button
                      key={item.action}
                      size="sm"
                      variant={item.danger ? 'danger' : 'secondary'}
                      disabled={user.account_status === (item.action === 'activate' ? 'ACTIVE' : item.action.toUpperCase())}
                      onClick={() => {
                        setActionError(null);
                        setConfirmAction(item);
                      }}
                    >
                      {item.label}
                    </Button>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* Wallet (§14) — backend-computed values only */}
          <section className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
            <h2 className="mb-3 text-sm font-semibold text-white">Wallet</h2>
            <div className="grid gap-3 text-sm sm:grid-cols-3 xl:grid-cols-6">
              {[
                ['Total', user.wallet.total_balance],
                ['Deposit', user.wallet.deposit_balance],
                ['Withdrawable', user.wallet.withdrawable_balance],
                ['Pending', user.wallet.pending_balance],
                ['Locked', user.wallet.locked_balance],
                ['Bonus', user.wallet.bonus_balance],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl bg-surface-200/40 p-3">
                  <p className="text-[11px] uppercase tracking-wide text-surface-500">{label}</p>
                  <p className="mt-0.5 font-semibold tabular-nums text-white">{formatUsdt(value)} USDT</p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11px] text-surface-500">
              Balances are read-only. Any adjustment must go through a dedicated audited wallet operation — this panel intentionally provides none (§50).
            </p>
          </section>

          {/* History tabs (§14) */}
          <section className="rounded-2xl border border-surface-200 bg-surface-50 p-4">
            <div className="mb-3 flex flex-wrap gap-1.5">
              {TABS.map((item) => (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setTab(item.key)}
                  className={
                    tab === item.key
                      ? 'rounded-full bg-brand-600 px-3 py-1.5 text-xs font-semibold text-white'
                      : 'rounded-full bg-surface-200/40 px-3 py-1.5 text-xs font-semibold text-surface-300 hover:bg-surface-300/60'
                  }
                >
                  {item.label}
                </button>
              ))}
            </div>
            {historyQuery.isLoading ? (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="h-10 animate-pulse rounded-xl bg-surface-200/40" />
                ))}
              </div>
            ) : (historyQuery.data ?? []).length === 0 ? (
              <p className="py-6 text-center text-sm text-surface-500">No records.</p>
            ) : (
              <pre className="max-h-80 overflow-auto rounded-xl bg-surface-950/60 p-3 text-[11px] leading-relaxed text-surface-300">
                {JSON.stringify(historyQuery.data, null, 2)}
              </pre>
            )}
          </section>
        </div>
      )}

      {/* Confirmation modal (§15, §67) */}
      <Modal
        open={confirmAction !== null}
        onClose={() => {
          if (!busy) setConfirmAction(null);
        }}
        title={confirmAction ? `${confirmAction.verb} user` : ''}
        description="This action is audited and notifies the user."
      >
        {confirmAction && (
          <div className="space-y-4">
            <p className="text-sm text-surface-300">
              {confirmAction.action === 'activate'
                ? `Reactivate ${user?.email ?? 'this user'}?`
                : confirmAction.action === 'suspend'
                  ? `Suspend ${user?.email ?? 'this user'}? They will be signed out and unable to log in.`
                  : `Ban ${user?.email ?? 'this user'}? This blocks all access.`}
            </p>
            {confirmAction.needsReason && (
              <div>
                <label htmlFor="action-reason" className="mb-1 block text-xs font-medium text-surface-400">
                  Reason (required)
                </label>
                <textarea
                  id="action-reason"
                  value={reason}
                  rows={3}
                  maxLength={500}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full resize-none rounded-xl border border-surface-200 bg-surface-950 px-3 py-2.5 text-sm text-surface-100 focus:border-brand-500 focus:outline-none"
                />
              </div>
            )}
            {actionError && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{actionError}</p>}
            <div className="flex gap-2">
              <Button variant="secondary" fullWidth onClick={() => setConfirmAction(null)} disabled={busy}>
                Cancel
              </Button>
              <Button
                variant={confirmAction.danger ? 'danger' : 'primary'}
                fullWidth
                isLoading={busy}
                disabled={confirmAction.needsReason && reason.trim().length === 0}
                onClick={() => void runAction()}
              >
                Confirm
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
