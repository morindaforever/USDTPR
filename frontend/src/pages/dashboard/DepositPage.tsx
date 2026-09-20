import { useEffect, useState } from 'react';
import {
  ArrowDownToLine,
  Check,
  Copy,
  RefreshCw,
  TriangleAlert,
} from 'lucide-react';
import { Alert, Button, Card, Input, PageContainer } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { depositService } from '@/services/depositService';
import { cn } from '@/utils/cn';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { Deposit, DepositAddress, DepositNetwork } from '@/types';

/**
 * Deposit page (Section 15 §9): network → address → copy/QR → amount +
 * reference → submit → review status. Every financial value (minimum,
 * status, credit) is backend-authoritative; the page only collects input.
 * Deposits are reviewed by an admin.
 */

const STATUS_TONE: Record<string, 'warning' | 'success' | 'danger'> = {
  PENDING: 'warning',
  APPROVED: 'success',
  REJECTED: 'danger',
};

function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (permissions/insecure context) — user can
      // still select the text manually.
    }
  };

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => void copy()}
      aria-label={`${copied ? 'Copied' : `Copy ${label}`}`}
    >
      {copied ? (
        <Check className="h-4 w-4 text-emerald-600" aria-hidden />
      ) : (
        <Copy className="h-4 w-4" aria-hidden />
      )}
      {copied ? 'Copied' : 'Copy'}
    </Button>
  );
}

export function DepositPage() {
  const [networks, setNetworks] = useState<DepositNetwork[]>([]);
  const [selected, setSelected] = useState('');
  const [address, setAddress] = useState<DepositAddress | null>(null);
  const [addressLoading, setAddressLoading] = useState(false);
  const [addressError, setAddressError] = useState<string | null>(null);
  const [amount, setAmount] = useState('');
  const [reference, setReference] = useState('');
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [submitted, setSubmitted] = useState<Deposit | null>(null);
  const [minimum, setMinimum] = useState<string | null>(null);

  const history = useDashboardData<Deposit[]>(() => depositService.list());
  const selectedNetwork = networks.find((n) => n.code === selected) ?? null;

  useEffect(() => {
    let cancelled = false;
    depositService
      .networks()
      .then((rows) => {
        if (cancelled) return;
        setNetworks(rows);
        if (rows.length > 0) setSelected((cur) => cur || rows[0].code);
      })
      .catch(() => {
        if (!cancelled) setNetworks([]);
      });
    depositService
      .minimum()
      .then((value) => {
        if (!cancelled) setMinimum(value);
      })
      .catch(() => {
        /* backend re-validates at submit regardless */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    setAddressLoading(true);
    setAddressError(null);
    setAddress(null);
    depositService
      .address(selected)
      .then((data) => {
        if (!cancelled) setAddress(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setAddressError(err instanceof Error ? err.message : 'Unable to load deposit address.');
        }
      })
      .finally(() => {
        if (!cancelled) setAddressLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    setFieldErrors({});
    setSubmitted(null);
    try {
      const deposit = await depositService.submit({
        network: selected,
        amount,
        tx_hash: reference,
        order_id: '',
        screenshot,
      });
      setSubmitted(deposit);
      setAmount('');
      setReference('');
      setScreenshot(null);
      history.retry();
    } catch (err) {
      const fieldErrors = (err as { fieldErrors?: Record<string, string[]> }).fieldErrors;
      if (fieldErrors && Object.keys(fieldErrors).length > 0) {
        setFieldErrors(fieldErrors);
      } else {
        setFieldErrors({
          amount: [err instanceof Error ? err.message : 'Deposit submission failed.'],
        });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const onScreenshotChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setScreenshot(file);
    // Allow re-selecting the same file after a reset.
    event.target.value = '';
  };

  // Per-network minimum (backend-resolved) falls back to the global rules value.
  const effectiveMinimum = selectedNetwork?.minimum_amount ?? minimum;

  const rows = history.data ?? [];

  return (
    <PageContainer title="Deposit" subtitle="Fund your account with USDT.">
      <div className="space-y-5">
        <Alert tone="warning" title="Deposit Review">
          Deposits are reviewed manually by an administrator.
        </Alert>

        {/* Step 1 — network (§9) */}
        <Card>
          <div className="p-5">
            <h2 className="text-sm font-semibold text-surface-900">
              <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-[11px] font-bold text-white">1</span>
              Select network
            </h2>
            {networks.length === 0 ? (
              <p className="mt-3 text-sm text-surface-500">No networks available right now.</p>
            ) : (
              <div role="radiogroup" aria-label="Deposit network" className="mt-3 flex flex-wrap gap-2">
                {networks.map((network) => (
                  <button
                    key={network.code}
                    type="button"
                    role="radio"
                    aria-checked={selected === network.code}
                    onClick={() => setSelected(network.code)}
                    className={cn(
                      'rounded-xl border px-3.5 py-2 text-sm font-semibold transition-colors',
                      selected === network.code
                        ? 'border-brand-600 bg-brand-600 text-white'
                        : 'border-surface-200 bg-white text-surface-700 hover:bg-surface-50',
                    )}
                  >
                    {network.name}
                    <span className="ml-1.5 text-xs font-medium opacity-70">{network.code}</span>
                  </button>
                ))}
              </div>
            )}

            {selectedNetwork?.contract_address && (
              <p className="mt-3 break-all text-[11px] text-surface-500">
                <span className="font-medium text-surface-600">USDT contract:</span>{' '}
                <code className="rounded bg-surface-100 px-1.5 py-0.5">{selectedNetwork.contract_address}</code>
              </p>
            )}

            <div className="mt-4 rounded-xl bg-amber-50 p-3 ring-1 ring-inset ring-amber-200">
              <p className="flex items-start gap-2 text-xs leading-relaxed text-amber-900">
                <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                {selectedNetwork?.network_warning ||
                  'Send USDT only on the selected network. Sending assets through another network may result in permanent loss.'}
              </p>
            </div>
            {selectedNetwork?.instructions && (
              <p className="mt-2 text-xs leading-relaxed text-surface-500">{selectedNetwork.instructions}</p>
            )}
          </div>
        </Card>

        {/* Step 2 — address + QR (§9) */}
        <Card>
          <div className="p-5">
            <h2 className="text-sm font-semibold text-surface-900">
              <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-[11px] font-bold text-white">2</span>
              Deposit address {selected && <span className="text-surface-400">({selected})</span>}
            </h2>
            {addressLoading ? (
              <div className="mt-4 space-y-3">
                <Skeleton className="h-20 w-20 rounded-xl" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : addressError ? (
              <p role="alert" className="mt-3 text-sm text-red-600">{addressError}</p>
            ) : address ? (
              <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start">
                {/* Server-rendered QR — always matches the address shown. */}
                <img
                  src={address.qr_code}
                  alt={`QR code for deposit address ${address.address}`}
                  className="h-32 w-32 shrink-0 rounded-xl border border-surface-200 bg-white"
                />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-medium text-surface-500">Address</p>
                  <div className="mt-1 flex items-center gap-2">
                    <code className="min-w-0 flex-1 break-all rounded-lg bg-surface-50 px-3 py-2 text-xs text-surface-800">
                      {address.address}
                    </code>
                    <CopyButton value={address.address} label="deposit address" />
                  </div>
                  <p className="mt-2 text-[11px] text-surface-400">
                    The QR code is rendered from this exact address. Double-check
                    the network before sending.
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        </Card>

        {/* Step 3 — amount + reference (§9) */}
        <Card>
          <div className="p-5">
            <h2 className="text-sm font-semibold text-surface-900">
              <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-600 text-[11px] font-bold text-white">3</span>
              Submit deposit for review
            </h2>
            {effectiveMinimum && (
              <p className="mt-1 text-xs text-surface-500">
                Minimum deposit: {formatUsdt(effectiveMinimum)} USDT (validated by the backend).
              </p>
            )}
            <form onSubmit={(event) => void submit(event)} className="mt-4 space-y-4" noValidate>
              <Input
                label="Amount (USDT)"
                type="number"
                inputMode="decimal"
                min="0"
                step="0.01"
                name="amount"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
                error={fieldErrors.amount?.[0]}
                required
              />
              <Input
                label="Transaction hash or order reference"
                hint="Paste the tx hash or your order reference so the reviewer can match your transfer."
                name="reference"
                value={reference}
                onChange={(event) => setReference(event.target.value)}
                error={fieldErrors.tx_hash?.[0]}
                required
              />
              <div>
                <label
                  htmlFor="deposit-screenshot"
                  className="mb-1.5 block text-sm font-medium text-surface-700"
                >
                  Payment screenshot <span className="font-normal text-surface-400">(optional)</span>
                </label>
                <input
                  id="deposit-screenshot"
                  type="file"
                  accept="image/png,image/jpeg,image/webp"
                  onChange={onScreenshotChange}
                  className="block w-full cursor-pointer rounded-xl border border-surface-200 bg-white px-3 py-2.5 text-sm text-surface-600 file:mr-3 file:cursor-pointer file:rounded-lg file:border-0 file:bg-brand-50 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-brand-700 hover:file:bg-brand-100"
                />
                {screenshot && (
                  <p className="mt-1.5 text-xs text-surface-500">
                    Attached: {screenshot.name} ({Math.max(1, Math.round(screenshot.size / 1024))} KB)
                  </p>
                )}
                {fieldErrors.screenshot?.[0] && (
                  <p className="mt-1.5 text-xs text-red-600">{fieldErrors.screenshot[0]}</p>
                )}
              </div>
              <Button
                type="submit"
                fullWidth
                isLoading={submitting}
                disabled={submitting || !selected || selectedNetwork?.has_address === false}
              >
                Submit deposit request
              </Button>
            </form>

            {submitted && (
              <Alert tone="success" title="Deposit submitted successfully" className="mt-4">
                Request <strong>{submitted.deposit_id}</strong> is awaiting admin
                review. You will be notified when its status changes.
              </Alert>
            )}
          </div>
        </Card>

        {/* Review status (§9) */}
        <Card>
          <div className="p-5">
            <h2 className="text-sm font-semibold text-surface-900">Your deposits</h2>
            {history.isLoading ? (
              <div className="mt-4 space-y-2">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : history.error ? (
              <div className="mt-4 text-center">
                <p className="text-sm text-surface-600">{history.error}</p>
                <Button variant="outline" size="sm" className="mt-3" onClick={history.retry}>
                  <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                  Try again
                </Button>
              </div>
            ) : rows.length === 0 ? (
              <p className="mt-4 text-sm text-surface-500">
                No deposits yet — submitted requests and their review status will
                appear here.
              </p>
            ) : (
              <ul className="mt-4 divide-y divide-surface-100">
                {rows.map((deposit) => (
                  <li key={deposit.deposit_id} className="flex items-center gap-3 py-3">
                    <span
                      className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600"
                      aria-hidden
                    >
                      <ArrowDownToLine className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-surface-900">
                        {formatUsdt(deposit.amount)} USDT · {deposit.network}
                      </p>
                      <p className="text-[11px] text-surface-400">
                        {deposit.deposit_id} · {formatDateTime(deposit.submitted_at)}
                      </p>
                    </div>
                    <span
                      className={cn(
                        'rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide',
                        STATUS_TONE[deposit.status] === 'success' &&
                          'bg-emerald-50 text-emerald-700',
                        STATUS_TONE[deposit.status] === 'warning' &&
                          'bg-amber-50 text-amber-700',
                        STATUS_TONE[deposit.status] === 'danger' && 'bg-red-50 text-red-700',
                      )}
                    >
                      {deposit.status.toLowerCase()}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      </div>
    </PageContainer>
  );
}
