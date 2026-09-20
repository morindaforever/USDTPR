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
 * the server response on confirm remains authoritative. The user must
 * explicitly confirm after reviewing the network and destination.
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

        <div className="rounded-xl bg-sky-50 p-3 text-xs leading-relaxed text-sky-900 ring-1 ring-inset ring-sky-200">
          You are requesting to withdraw{' '}
          <strong>{quote ? `${formatUsdt(quote.amount)} USDT` : '—'}</strong> on{' '}
          <strong>{network ? `${network.name} (${network.code})` : '—'}</strong> to:
          <span className="mt-1 block break-all font-mono text-[11px]">{address}</span>
          Please verify the network and address before submitting. Transfers
          to a wrong network cannot be reversed.
        </div>

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
