import { useCallback, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminService } from '@/services/adminService';
import { Skeleton, useDashboardData } from '@/hooks';
import {
  AdminFilterChips,
  AdminMiniBarChart,
  AdminPageHeader,
  AdminStatCard,
  AdminStatusBadge,
} from '@/components/admin';
import type { AdminDashboard } from '@/types/admin';

type RangeKey = 'today' | '7d' | '30d' | 'all';

const RANGE_OPTIONS: Array<{ key: RangeKey; label: string }> = [
  { key: 'today', label: 'Today' },
  { key: '7d', label: '7 Days' },
  { key: '30d', label: '30 Days' },
  { key: 'all', label: 'All Time' },
];

/** Admin dashboard (§7–9): every number is backend-aggregated (§80). */
export function AdminDashboardPage() {
  const [range, setRange] = useState<RangeKey>('all');
  const fetcher = useCallback(
    async (): Promise<AdminDashboard> => {
      const envelope = await adminService.dashboard(range);
      if (!envelope.success || !envelope.data) throw new Error(envelope.message || 'Unable to load dashboard.');
      return envelope.data;
    },
    [range],
  );
  const query = useDashboardData<AdminDashboard>(fetcher);
  const data = query.data;

  return (
    <div>
      <AdminPageHeader
        title="Dashboard"
        subtitle="Platform overview — financial metrics and activity."
        actions={<AdminFilterChips options={RANGE_OPTIONS} value={range} onChange={setRange} />}
      />

      {query.isLoading ? (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {[0, 1, 2, 3, 4, 5, 6, 7].map((i) => (
            <Skeleton key={i} className="h-24 w-full rounded-2xl bg-white/5" />
          ))}
        </div>
      ) : query.error || !data ? (
        <div className="rounded-2xl border border-white/10 bg-surface-900 p-6 text-center text-sm text-surface-300">
          {query.error || 'Unable to load dashboard.'}
        </div>
      ) : (
        <div className="space-y-6">
          {/* Core counts (§7) */}
          <section aria-label="User statistics">
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <AdminStatCard label="Total Users" value={data.total_users} />
              <AdminStatCard label="Active Users" value={data.active_users} />
              <AdminStatCard label="Pending Deposits" value={data.pending.pending_deposits} tone={data.pending.pending_deposits > 0 ? 'warning' : 'default'} />
              <AdminStatCard label="Pending Withdrawals" value={data.pending.pending_withdrawals} tone={data.pending.pending_withdrawals > 0 ? 'warning' : 'default'} />
              <AdminStatCard label="Active VIP Purchases" value={data.pending.active_vip_purchases} />
              <AdminStatCard label="Open Support" value={data.pending.open_support} tone={data.pending.open_support > 0 ? 'warning' : 'default'} />
              <AdminStatCard label="Rewards Credited" value={`${data.financial_metrics.rewards_credited.amount} USDT`} hint={`${data.financial_metrics.rewards_credited.count} in range`} />
              <AdminStatCard label="Commissions" value={`${data.financial_metrics.commissions_credited.amount} USDT`} hint={`${data.financial_metrics.commissions_credited.count} in range`} />
            </div>
          </section>

          {/* Real financial activity (§15/§16) — actual DB aggregates. */}
          <div className="rounded-2xl border border-surface-700 bg-surface-900 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-surface-300">
              {data.financial_metrics.label}
            </p>
            <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2 xl:grid-cols-5">
              {[
                ['Deposits submitted', data.financial_metrics.deposits_submitted],
                ['Withdrawals requested', data.financial_metrics.withdrawals_requested],
                ['VIP purchases', data.financial_metrics.vip_purchases],
                ['Rewards credited', data.financial_metrics.rewards_credited],
                ['Commissions credited', data.financial_metrics.commissions_credited],
              ].map(([label, metric]) => {
                const m = metric as { count: number; amount?: string; investment?: string };
                return (
                  <div key={label as string} className="rounded-xl bg-surface-900 p-3">
                    <p className="text-[11px] text-surface-400">{label as string}</p>
                    <p className="mt-0.5 font-semibold tabular-nums text-white">
                      {m.amount ?? m.investment} USDT
                    </p>
                    <p className="text-[11px] text-surface-500">{m.count} in range</p>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Registrations chart (§9) */}
          {data.registrations.length > 0 && (
            <section aria-label="Registrations" className="rounded-2xl border border-white/10 bg-surface-900 p-4">
              <h2 className="mb-3 text-sm font-semibold text-white">User registrations per day</h2>
              <AdminMiniBarChart data={data.registrations} />
            </section>
          )}

          {/* Recent users */}
          <section aria-label="Recent users" className="rounded-2xl border border-white/10 bg-surface-900 p-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white">Newest users</h2>
              <Link to="/admin/users" className="text-xs font-semibold text-brand-300 hover:text-brand-200">
                View all →
              </Link>
            </div>
            <ul className="divide-y divide-white/5">
              {data.recent_users.map((user) => (
                <li key={user.user_id} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <Link to={`/admin/users/${user.user_id}`} className="truncate text-sm font-medium text-surface-200 hover:text-brand-300">
                      {user.full_name || user.email}
                    </Link>
                    <p className="font-mono text-[11px] text-surface-500">{user.user_id}</p>
                  </div>
                  <AdminStatusBadge status={user.account_status} />
                </li>
              ))}
            </ul>
          </section>
        </div>
      )}
    </div>
  );
}
