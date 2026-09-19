import { formatDate, formatUsdt } from '@/utils/format';
import type { ReferralCommission } from '@/types';

const STATUS_TONES: Record<ReferralCommission['status'], string> = {
  PENDING: 'bg-amber-50 text-amber-700 ring-amber-200',
  CREDITED: 'bg-brand-50 text-brand-700 ring-brand-200',
  FAILED: 'bg-red-50 text-red-700 ring-red-200',
  REVERSED: 'bg-surface-100 text-surface-500 ring-surface-200',
};

/**
 * Commission history list (§28/§33): every row is a persisted backend
 * record — amount, rate, level, status, ledger reference.
 */
export function CommissionHistory({ commissions }: { commissions: ReferralCommission[] }) {
  if (commissions.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-surface-200 p-5 text-center text-sm text-surface-500">
        No commissions yet. Commissions accrue when your team earns VIP rewards.
      </p>
    );
  }
  return (
    <ul className="space-y-2.5">
      {commissions.map((commission) => (
        <li
          key={commission.commission_id}
          className="flex items-center justify-between gap-3 rounded-2xl border border-surface-200 bg-white p-4"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-surface-900">
              Level {commission.level} commission
              <span className="ml-2 font-mono text-[11px] font-normal text-surface-400">
                {commission.commission_id}
              </span>
            </p>
            <p className="mt-0.5 truncate text-xs text-surface-500">
              from {commission.source_user_id} · {formatDate(commission.created_at)}
              {commission.transaction_id ? (
                <>
                  {' · '}
                  <span className="font-mono">{commission.transaction_id}</span>
                </>
              ) : null}
            </p>
          </div>
          <div className="shrink-0 text-right">
            <p className="text-sm font-semibold tabular-nums text-brand-700">
              +{formatUsdt(commission.commission_amount)} USDT
            </p>
            <span
              className={`mt-0.5 inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${STATUS_TONES[commission.status] ?? STATUS_TONES.PENDING}`}
            >
              {commission.status}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
