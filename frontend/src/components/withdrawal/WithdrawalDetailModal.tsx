import { Badge } from '@/components/Badge';
import { Modal } from '@/components/Modal';
import { formatDate, formatUsdt } from '@/utils/format';
import { withdrawalStatusTone } from './withdrawalDisplay';

import type { WithdrawalDetail } from '@/types';

interface WithdrawalDetailModalProps {
  withdrawal: WithdrawalDetail | null;
  isLoading?: boolean;
  onClose: () => void;
}

const STATUS_LABELS: Record<WithdrawalDetail['status'], string> = {
  PENDING: 'Pending review',
  APPROVED: 'Approved — awaiting processing',
  REJECTED: 'Rejected',
  PROCESSING: 'Processing',
  COMPLETED: 'Completed',
  FAILED: 'Failed — funds released',
};

const TIMELINE_STEPS: Array<{
  key: 'created_at' | 'approved_at' | 'processing_at' | 'completed_at' | 'rejected_at' | 'failed_at';
  label: string;
}> = [
  { key: 'created_at', label: 'Requested' },
  { key: 'approved_at', label: 'Approved' },
  { key: 'processing_at', label: 'Processing started' },
  { key: 'completed_at', label: 'Completed' },
  { key: 'rejected_at', label: 'Rejected' },
  { key: 'failed_at', label: 'Failed' },
];

/** Withdrawal detail (§39, §44): full destination is owner-visible here. */
export function WithdrawalDetailModal({ withdrawal, isLoading = false, onClose }: WithdrawalDetailModalProps) {
  return (
    <Modal
      open={withdrawal !== null || isLoading}
      onClose={onClose}
      title="Withdrawal Details"
      description={withdrawal?.withdrawal_id}
    >
      {isLoading || !withdrawal ? (
        <div className="space-y-3 py-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-10 animate-pulse rounded-xl bg-surface-100" />
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-2xl font-bold tabular-nums text-surface-800">
                −{formatUsdt(withdrawal.amount)} USDT
              </p>
              <p className="mt-0.5 text-xs text-surface-500">
                Fee {formatUsdt(withdrawal.fee_amount)} · You receive{' '}
                {formatUsdt(withdrawal.net_amount)} USDT
              </p>
            </div>
            <Badge tone={withdrawalStatusTone(withdrawal.status)}>
              {STATUS_LABELS[withdrawal.status] ?? withdrawal.status}
            </Badge>
          </div>

          <dl className="space-y-3 rounded-xl bg-surface-50 p-4 text-sm">
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">
                Network
              </dt>
              <dd className="mt-0.5 font-semibold text-surface-800">{withdrawal.network_name}</dd>
            </div>
            <div>
              <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">
                Destination
              </dt>
              <dd className="mt-0.5 break-all font-mono text-xs text-surface-800">
                {withdrawal.destination_address || withdrawal.masked_address}
              </dd>
            </div>
            {withdrawal.status === 'COMPLETED' && withdrawal.tx_hash && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">
                  Transaction Reference
                </dt>
                <dd className="mt-0.5 break-all font-mono text-xs text-surface-800">
                  {withdrawal.tx_hash}
                </dd>
              </div>
            )}
            {withdrawal.rejection_reason && (
              <div>
                <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">
                  Rejection Reason
                </dt>
                <dd className="mt-0.5 text-sm text-danger-700">{withdrawal.rejection_reason}</dd>
              </div>
            )}
          </dl>

          {/* Status timeline */}
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-surface-500">
              Timeline
            </p>
            <ul className="space-y-2">
              {TIMELINE_STEPS.filter(
                (step) => withdrawal[step.key] !== null,
              ).map((step) => (
                <li key={step.key} className="flex items-center justify-between text-sm">
                  <span className="text-surface-600">{step.label}</span>
                  <span className="tabular-nums text-surface-800">
                    {formatDate(withdrawal[step.key] as string)}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Modal>
  );
}
