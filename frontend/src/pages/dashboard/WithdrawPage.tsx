import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, ArrowUpFromLine, Crown, Info, Lock } from 'lucide-react';

import { Alert, PageContainer } from '@/components';
import {
  NetworkSelector,
  WithdrawalConfirmModal,
  WithdrawalDetailModal,
  WithdrawalForm,
  WithdrawalHistory,
} from '@/components/withdrawal';
import { Skeleton, useDashboardData } from '@/hooks';
import { withdrawalService } from '@/services/withdrawalService';
import { formatUsdt } from '@/utils/format';
import type {
  Withdrawal,
  WithdrawalDetail,
  WithdrawalNetwork,
  WithdrawalQuote,
  WithdrawalRules,
  WithdrawalSummary,
} from '@/types';

/**
 * Withdrawal page (Section 10). The backend is authoritative for the
 * withdrawable balance, minimum, fee, and net amount — the frontend only
 * collects the network, address, and amount and displays server quotes.
 */
export function WithdrawPage() {
  const navigate = useNavigate();

  // Server data
  const networksQuery = useDashboardData<WithdrawalNetwork[]>(() => withdrawalService.networks());
  const summaryQuery = useDashboardData<WithdrawalSummary>(() => withdrawalService.summary());
  const rulesQuery = useDashboardData<WithdrawalRules>(() => withdrawalService.rules());
  const historyQuery = useDashboardData<Withdrawal[]>(
    () => withdrawalService.list().then((r) => r.data ?? []),
  );

  // Form state
  const [networkCode, setNetworkCode] = useState<string | null>(null);
  const [address, setAddress] = useState('');
  const [amount, setAmount] = useState('');
  const [qrImage, setQrImage] = useState<File | null>(null);
  const [quote, setQuote] = useState<WithdrawalQuote | null>(null);

  // Confirmation + submission state
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [lastWithdrawalId, setLastWithdrawalId] = useState<string | null>(null);

  // Detail modal state
  const [detail, setDetail] = useState<WithdrawalDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const networks = networksQuery.data ?? [];
  const summary = summaryQuery.data ?? null;
  const selectedNetwork = useMemo(
    () => networks.find((n) => n.code === networkCode) ?? null,
    [networks, networkCode],
  );

  const addressError = useMemo(() => {
    if (!selectedNetwork || address.trim().length === 0) return null;
    if (address.trim().length < 20) return 'That address looks too short for this network.';
    return null;
  }, [selectedNetwork, address]);

  const amountError = useMemo(() => {
    const trimmed = amount.trim();
    if (trimmed.length === 0) return null;
    const value = Number(trimmed);
    if (Number.isNaN(value) || value <= 0) return 'Enter a valid amount.';
    if (summary && value > Number(summary.withdrawable_balance)) {
      return (
        `Amount exceeds your withdrawable balance (${formatUsdt(summary.withdrawable_balance)} USDT). ` +
        'Only VIP plan profits and referral commissions are withdrawable.'
      );
    }
    return null;
  }, [amount, summary]);

  // Debounced server quote whenever amount/network changes (§47).
  useEffect(() => {
    const trimmed = amount.trim();
    if (!networkCode || trimmed.length === 0 || Number.isNaN(Number(trimmed))) {
      setQuote(null);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(() => {
      withdrawalService
        .quote(trimmed, networkCode)
        .then((data) => {
          if (!cancelled) setQuote(data);
        })
        .catch(() => {
          if (!cancelled) setQuote(null);
        });
    }, 400);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [amount, networkCode]);

  const openDetail = useCallback(async (withdrawalId: string) => {
    setDetail(null);
    setDetailLoading(true);
    try {
      const data = await withdrawalService.detail(withdrawalId);
      setDetail(data);
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  const submitWithdrawal = useCallback(async () => {
    if (!networkCode || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const idempotencyKey = `web-wdr-${crypto.randomUUID()}`;
      const envelope = await withdrawalService.create({
        network: networkCode,
        destination_address: address.trim(),
        amount,
        idempotency_key: idempotencyKey,
        qr_image: qrImage,
      });
      if (!envelope.success || !envelope.data) {
        setSubmitError(envelope.message || 'Unable to submit the withdrawal.');
        return;
      }
      setLastWithdrawalId(envelope.data.withdrawal_id);
      setConfirmOpen(false);
      setAmount('');
      setAddress('');
      setQrImage(null);
      setQuote(null);
      historyQuery.retry();
      summaryQuery.retry();
    } catch (err: unknown) {
      setSubmitError(
        err instanceof Error ? err.message : 'Unable to submit the withdrawal. Please try again.',
      );
    } finally {
      setSubmitting(false);
    }
  }, [networkCode, address, amount, qrImage, submitting, historyQuery, summaryQuery]);

  const handleMax = useCallback(() => {
    if (summary && Number(summary.withdrawable_balance) > 0) {
      setAmount(summary.withdrawable_balance);
    }
  }, [summary]);

  const loadingAny = networksQuery.isLoading || summaryQuery.isLoading;
  const minimumAmount = quote?.minimum_amount ?? rulesQuery.data?.minimum_amount ?? null;

  // Server-computed eligibility: a paid VIP plan (VIP 1+) is required to
  // withdraw; the Welcome Plan does not qualify. The frontend notice is a
  // convenience — the backend enforces the same rule on submission.
  const withdrawAllowed = summary ? summary.can_withdraw !== false : null;

  return (
    <PageContainer
      title="Withdraw"
      subtitle="Request a withdrawal from your available balance."
      actions={
        <button
          type="button"
          onClick={() => navigate('/home')}
          className="inline-flex items-center gap-1.5 rounded-xl border border-surface-200 px-3.5 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          Back to Dashboard
        </button>
      }
    >
      <div className="space-y-6">
        {/* Notice */}
        <div className="flex gap-3 rounded-xl bg-sky-50 p-3.5 text-sky-900 ring-1 ring-inset ring-sky-200">
          <Info className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
          <div className="text-sm">
            <p className="font-semibold">Withdrawable balance rules</p>
            <p className="mt-0.5 opacity-90">
              Withdrawals can only use your <strong>withdrawable balance</strong> — funded by VIP plan
              profits and referral commissions. Your deposit balance is used to buy VIP plans and cannot
              be withdrawn. Requests are reviewed and processed manually by the platform team and lock
              your funds immediately.
            </p>
          </div>
        </div>

        {/* Balance card — all values backend-computed (§6) */}
        <section className="rounded-2xl bg-gradient-to-br from-brand-700 to-brand-900 p-5 text-white shadow-card">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-brand-200">
                Withdrawable Balance
              </p>
              {summaryQuery.isLoading ? (
                <div className="mt-1.5 h-8 w-32 animate-pulse rounded-lg bg-white/20" />
              ) : (
                <p className="mt-1 text-3xl font-bold tabular-nums">
                  {summary ? formatUsdt(summary.withdrawable_balance) : '—'}{' '}
                  <span className="text-base font-semibold text-brand-200">USDT</span>
                </p>
              )}
            </div>
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10">
              <ArrowUpFromLine className="h-5 w-5" aria-hidden />
            </div>
          </div>
          {summary && Number(summary.pending_withdrawals) > 0 && (
            <div className="mt-4 flex items-center justify-between rounded-xl bg-white/10 px-4 py-3">
              <span className="flex items-center gap-2 text-sm text-brand-100">
                <Lock className="h-4 w-4" aria-hidden />
                Pending Withdrawals
              </span>
              <span className="text-sm font-semibold tabular-nums">
                {formatUsdt(summary.pending_withdrawals)} USDT
              </span>
            </div>
          )}
        </section>

        {/* Zero-withdrawable explainer — deposits are for plans, not payouts */}
        {summary && Number(summary.withdrawable_balance) <= 0 && (
          <Alert tone="warning" title="No withdrawable balance yet">
            Your withdrawable balance is 0.00 USDT. It grows as your VIP plan profits and referral
            commissions are credited. Deposit balance is used to purchase VIP plans and cannot be
            withdrawn.
          </Alert>
        )}

        {/* Withdrawal request form (hidden while ineligible) */}
        <section aria-labelledby="request-heading" className="rounded-2xl border border-surface-200 bg-white p-5">
          <h2 id="request-heading" className="mb-4 text-sm font-semibold text-surface-900">
            New Withdrawal Request
          </h2>
          {withdrawAllowed === false ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5">
              <p className="text-sm font-semibold text-amber-900">Withdrawal unavailable</p>
              <p className="mt-1 text-sm leading-relaxed text-amber-800">
                You must purchase at least VIP 1 to submit a withdrawal request.
              </p>
              <p className="mt-1 text-sm leading-relaxed text-amber-800">
                The Welcome Plan does not qualify for withdrawal eligibility.
              </p>
              <button
                type="button"
                onClick={() => navigate('/vip')}
                className="mt-4 inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700"
              >
                <Crown className="h-4 w-4" aria-hidden />
                View VIP Plans
              </button>
            </div>
          ) : loadingAny ? (
            <div className="space-y-4">
              <Skeleton className="h-24 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : networksQuery.error || summaryQuery.error ? (
            <Alert tone="danger" title="Unable to load withdrawal data">
              Please try refreshing the page.
            </Alert>
          ) : (
            <>
              <p className="mb-2 text-sm font-medium text-surface-700">Select Network</p>
              <NetworkSelector
                networks={networks}
                value={networkCode}
                onChange={(code) => {
                  setNetworkCode(code);
                  setAddress('');
                  setQrImage(null);
                  setQuote(null);
                }}
              />
              <div className="mt-5">
                <WithdrawalForm
                  network={selectedNetwork}
                  address={address}
                  amount={amount}
                  quote={quote}
                  summary={summary}
                  minimumAmount={minimumAmount}
                  addressError={addressError}
                  amountError={amountError}
                  onAddressChange={setAddress}
                  onAmountChange={setAmount}
                  onMax={handleMax}
                  onSubmit={() => {
                    setSubmitError(null);
                    if (amountError) return; // validity/balance guard — the backend re-validates
                    setConfirmOpen(true);
                  }}
                />
              </div>

              {/* Optional QR destination image (§7) — the typed address
                  above remains the authoritative destination. */}
              <div className="mt-5">
                <label
                  htmlFor="withdrawal-qr"
                  className="mb-1.5 block text-sm font-medium text-surface-700"
                >
                  Wallet QR image <span className="font-normal text-surface-400">(optional)</span>
                </label>
                <input
                  id="withdrawal-qr"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={(event) => {
                    setQrImage(event.target.files?.[0] ?? null);
                    event.target.value = '';
                  }}
                  className="block w-full cursor-pointer rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-600 file:mr-3 file:cursor-pointer file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-brand-700 hover:file:bg-brand-100"
                />
                {qrImage && (
                  <p className="mt-1.5 text-xs text-surface-500">
                    Attached: {qrImage.name} — reviewers see this for context;
                    the typed address is always the payout destination.
                  </p>
                )}
              </div>
            </>
          )}
        </section>

        {/* History */}
        <section aria-labelledby="history-heading">
          <h2 id="history-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Withdrawal History
          </h2>
          <WithdrawalHistory
            withdrawals={historyQuery.data ?? []}
            isLoading={historyQuery.isLoading}
            onSelect={(id) => void openDetail(id)}
          />
        </section>

        {lastWithdrawalId && (
          <Alert tone="success" title="Withdrawal request submitted">
            Your request {lastWithdrawalId.slice(0, 8)}… is pending review. Funds are locked until
            an administrator approves or rejects it.
          </Alert>
      )}
      </div>

      <WithdrawalConfirmModal
        open={confirmOpen}
        network={selectedNetwork}
        address={address}
        quote={quote}
        isSubmitting={submitting}
        errorMessage={submitError}
        onConfirm={() => void submitWithdrawal()}
        onClose={() => setConfirmOpen(false)}
      />

      <WithdrawalDetailModal
        withdrawal={detail}
        isLoading={detailLoading}
        onClose={() => {
          setDetail(null);
        }}
      />
    </PageContainer>
  );
}
