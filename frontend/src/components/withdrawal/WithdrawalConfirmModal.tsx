import { Alert, Button, Modal } from '@/components';
import { formatUsdt } from '@/utils/format';

import type { WithdrawalNetwork, WithdrawalQuote } from '@/types';

interface WithdrawalConfirmModalProps {
  open: boolean;
  network: WithdrawalNetwork | null;
  address: string;
  quote: WithdrawalQuote | null;
  isSubmitting: boolean;
  errorMessage: string | null;
  onConfirm: () => void;
  onClose: () => void;
}

/**
 * Confirmation dialog (§17). Shows the exact figures the backend quoted;
 * the server response on confirm remains authoritative.
 */
export function WithdrawalConfirmModal({
  open,
  network,
  address,
  quote,
  isSubmitting,
  errorMessage,
  onConfirm,
  onClose,
}: WithdrawalConfirmModalProps) {
  return (
    <Modal
      open={open}
      onClose={() => {
        if (!isSubmitting) onClose();
      }}
      title="Confirm Withdrawal"
      description="Please review the details before confirming."
    >
      <div className="space-y-4">
        <dl className="space-y-3">
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">
              Network
            </dt>
            <dd className="mt-0.5 text-sm font-semibold text-surface-900">
              {network ? `${network.name} (${network.code})` : '—'}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-medium uppercase tracking-wide text-surface-500">
              Destination
            </dt>
            <dd className="mt-0.5 break-all font-mono text-xs font-medium text-surface-900">
              {address}
            </dd>
          </div>
          {quote && (
            <>
              <div className="grid grid-cols-3 gap-2 rounded-xl bg-surface-50 p-3">
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
                    Amount
                  </dt>
                  <dd className="mt-0.5 text-sm font-semibold tabular-nums text-surface-900">
                    {formatUsdt(quote.amount)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
                    Fee
                  </dt>
                  <dd className="mt-0.5 text-sm font-semibold tabular-nums text-surface-900">
                    {formatUsdt(quote.fee)}
                  </dd>
                </div>
                <div>
                  <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
                    You Receive
                  </dt>
                  <dd className="mt-0.5 text-sm font-semibold tabular-nums text-brand-700">
                    {formatUsdt(quote.net_amount)}
                  </dd>
                </div>
              </div>
            </>
          )}
        </dl>

        {errorMessage && (
          <Alert tone="danger" title="Submission failed">
            {errorMessage}
          </Alert>
        )}

        <div className="flex gap-2">
          <Button
            variant="secondary"
            fullWidth
            onClick={onClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button fullWidth onClick={onConfirm} isLoading={isSubmitting}>
            Confirm Withdrawal
          </Button>
        </div>
      </div>
    </Modal>
  );
}
