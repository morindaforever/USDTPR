import { ClipboardPaste } from 'lucide-react';

import { Alert, Button } from '@/components';
import { formatUsdt } from '@/utils/format';
import type { WithdrawalNetwork, WithdrawalQuote, WithdrawalSummary } from '@/types';

interface WithdrawalFormProps {
  network: WithdrawalNetwork | null;
  address: string;
  amount: string;
  quote: WithdrawalQuote | null;
  summary: WithdrawalSummary | null;
  /** Backend-published minimum (rules endpoint or quote) — never frontend-derived. */
  minimumAmount: string | null;
  addressError: string | null;
  amountError: string | null;
  onAddressChange: (value: string) => void;
  onAmountChange: (value: string) => void;
  onMax: () => void;
  onSubmit: () => void;
}

/**
 * Address + amount entry (§9–15). Amounts are strings end-to-end — the
 * backend does all Decimal math; the Max button uses the backend balance.
 */
export function WithdrawalForm({
  network,
  address,
  amount,
  quote,
  summary,
  minimumAmount,
  addressError,
  amountError,
  onAddressChange,
  onAmountChange,
  onMax,
  onSubmit,
}: WithdrawalFormProps) {
  const paste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) onAddressChange(text.trim());
    } catch {
      // Clipboard permission denied — user can type manually.
    }
  };

  const submitDisabled =
    !network || address.trim().length === 0 || amount.trim().length === 0 || !!amountError;

  return (
    <div className="space-y-5">
      {/* Destination address */}
      <div>
        <label
          htmlFor="withdrawal-address"
          className="mb-1.5 block text-sm font-medium text-surface-700"
        >
          Destination Wallet Address
        </label>
        <div className="relative">
          <input
            id="withdrawal-address"
            type="text"
            inputMode="text"
            autoComplete="off"
            spellCheck={false}
            value={address}
            disabled={!network}
            onChange={(event) => onAddressChange(event.target.value)}
            placeholder={network?.address_hint || 'Select a network first'}
            className="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 pr-20 text-sm text-surface-900 placeholder:text-surface-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:bg-surface-50 disabled:text-surface-400"
          />
          <button
            type="button"
            onClick={() => void paste()}
            disabled={!network}
            className="absolute right-2 top-1/2 -translate-y-1/2 inline-flex items-center gap-1 rounded-lg bg-surface-100 px-2.5 py-1.5 text-xs font-semibold text-surface-600 transition-colors hover:bg-surface-200 disabled:opacity-50"
          >
            <ClipboardPaste className="h-3.5 w-3.5" aria-hidden />
            Paste
          </button>
        </div>
        {addressError ? (
          <p className="mt-1.5 text-xs text-red-600">{addressError}</p>
        ) : (
          <p className="mt-1.5 text-xs text-surface-400">
            Format validation only — {network?.name ?? 'the network'} address is not verified
            on-chain.
          </p>
        )}
      </div>

      {/* Amount */}
      <div>
        <div className="mb-1.5 flex items-center justify-between">
          <label htmlFor="withdrawal-amount" className="text-sm font-medium text-surface-700">
            Withdrawal Amount
          </label>
          <button
            type="button"
            onClick={onMax}
            disabled={!summary || Number(summary.withdrawable_balance) <= 0}
            className="rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700 transition-colors hover:bg-brand-100 disabled:opacity-50"
          >
            Max
          </button>
        </div>
        <div className="relative">
          <input
            id="withdrawal-amount"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            value={amount}
            disabled={!network}
            onChange={(event) => onAmountChange(event.target.value)}
            placeholder="0.00"
            className="w-full rounded-xl border border-surface-200 bg-white px-4 py-3 pr-16 text-sm font-semibold tabular-nums text-surface-900 placeholder:font-normal placeholder:text-surface-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 disabled:bg-surface-50 disabled:text-surface-400"
          />
          <span className="absolute right-4 top-1/2 -translate-y-1/2 text-sm font-medium text-surface-400">
            USDT
          </span>
        </div>
        {amountError ? (
          <p className="mt-1.5 text-xs text-red-600">{amountError}</p>
        ) : (
          <p className="mt-1.5 text-xs text-surface-400">
            Minimum withdrawal:{' '}
            {minimumAmount ? `${formatUsdt(minimumAmount)} USDT` : 'loading…'}
          </p>
        )}
      </div>

      {/* Fee / net summary — backend-quoted (§14–15) */}
      {quote && (
        <dl className="space-y-2 rounded-xl bg-surface-50 p-4 text-sm">
          <div className="flex items-center justify-between">
            <dt className="text-surface-500">Amount</dt>
            <dd className="font-medium tabular-nums text-surface-900">
              {formatUsdt(quote.amount)} USDT
            </dd>
          </div>
          <div className="flex items-center justify-between">
            <dt className="text-surface-500">Network Fee</dt>
            <dd className="font-medium tabular-nums text-surface-900">
              {formatUsdt(quote.fee)} USDT
            </dd>
          </div>
          <div className="flex items-center justify-between border-t border-surface-200 pt-2">
            <dt className="font-semibold text-surface-900">You Receive</dt>
            <dd className="font-semibold tabular-nums text-brand-700">
              {formatUsdt(quote.net_amount)} USDT
            </dd>
          </div>
        </dl>
      )}

      {/* Network warning (§11) */}
      {network && (
        <Alert tone="warning" title="Important">
          Only send/withdraw USDT using the {network.name} ({network.code}) network. Using an
          incompatible network may result in loss of funds.
        </Alert>
      )}

      <Button fullWidth size="lg" disabled={submitDisabled} onClick={onSubmit}>
        Review Withdrawal
      </Button>
    </div>
  );
}
