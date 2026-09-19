import { formatUsdt, formatDate } from '@/utils/format';
import { Badge } from '@/components/Badge';
import { withdrawalStatusTone } from './withdrawalDisplay';

import type { Withdrawal } from '@/types';

interface WithdrawalHistoryProps {
  withdrawals: Withdrawal[];
  isLoading?: boolean;
  onSelect: (withdrawalId: string) => void;
}

const STATUS_LABELS: Record<Withdrawal['status'], string> = {
  PENDING: 'Pending review',
  APPROVED: 'Approved',
  REJECTED: 'Rejected',
  PROCESSING: 'Processing',
  COMPLETED: 'Completed',
  FAILED: 'Failed',
};

/** Withdrawal history list (§38) — masked destinations, status, signed amounts. */
export function WithdrawalHistory({ withdrawals, isLoading = false, onSelect }: WithdrawalHistoryProps) {
  if (isLoading) {
    return (
      <div className="space-y-2.5">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-20 animate-pulse rounded-xl bg-surface-100" />
        ))}
      </div>
    );
  }

  if (withdrawals.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-surface-200 p-6 text-center">
        <p className="text-sm text-surface-500">No withdrawals yet.</p>
        <p className="mt-1 text-xs text-surface-400">
          Submitted withdrawal requests will appear here with their review status.
        </p>
      </div>
    );
  }

  return (
    <ul className="divide-y divide-surface-100 overflow-hidden rounded-2xl border border-surface-200 bg-white">
      {withdrawals.map((withdrawal) => (
        <li key={withdrawal.withdrawal_id}>
          <button
            type="button"
            onClick={() => onSelect(withdrawal.withdrawal_id)}
            className="flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-surface-50"
          >
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-semibold text-surface-900">
                  −{formatUsdt(withdrawal.amount)} USDT
                </span>
                <Badge tone={withdrawalStatusTone(withdrawal.status)}>
                  {STATUS_LABELS[withdrawal.status] ?? withdrawal.status}
                </Badge>
              </div>
              <p className="mt-0.5 truncate text-xs text-surface-500">
                {withdrawal.network_name} · {withdrawal.masked_address}
              </p>
              <p className="text-[11px] text-surface-400">{formatDate(withdrawal.created_at)}</p>
            </div>
            <div className="shrink-0 text-right">
              <p className="text-xs font-medium text-surface-500">
                receive {formatUsdt(withdrawal.net_amount)}
              </p>
            </div>
          </button>
        </li>
      ))}
    </ul>
  );
}
