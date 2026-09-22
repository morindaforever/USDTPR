import { Link, useParams } from 'react-router-dom';
import { ArrowDownLeft, ArrowUpRight, ArrowLeft } from 'lucide-react';
import { Badge, Card, ErrorState, PageContainer } from '@/components';
import { useDashboardData } from '@/hooks';
import { walletService } from '@/services/walletService';
import { cn } from '@/utils/cn';
import { formatDateTime, formatUsdt } from '@/utils/format';
import type { WalletTransaction } from '@/types';

/**
 * Transaction detail (Section 13 §25–26). Shows only the safe fields the
 * ledger serializer exposes; the exact timestamp is always visible (§36).
 * Related-record links (§27) map reference_type → the user-facing page —
 * admin-only surfaces are never linked.
 */

const TYPE_LABELS: Record<string, string> = {
  DEPOSIT: 'Deposit',
  WITHDRAWAL: 'Withdrawal',
  VIP_PURCHASE: 'VIP purchase',
  VIP_REWARD: 'Reward',
  REFERRAL_COMMISSION: 'Commission',
  WELCOME_BONUS: 'Welcome bonus',
  REFUND: 'Refund',
  ADJUSTMENT: 'Adjustment',
  LOCK: 'Lock (withdrawable → locked)',
  RELEASE: 'Release (locked → withdrawable)',
  TRANSFER: 'Internal bucket transfer',
};

/** §27: contextual link to the owning feature page (no admin pages). */
const REFERENCE_LINKS: Record<string, { to: string; label: string }> = {
  deposit: { to: '/deposit', label: 'View deposit' },
  withdrawal: { to: '/withdraw', label: 'View withdrawal' },
  vip_purchase: { to: '/vip', label: 'View VIP plan' },
  vip_reward: { to: '/vip', label: 'View rewards' },
  referral_commission: { to: '/team', label: 'View team commissions' },
};

function statusTone(status: string): 'success' | 'warning' | 'neutral' | 'danger' {
  if (status === 'COMPLETED') return 'success';
  if (status === 'PENDING') return 'warning';
  if (status === 'REVERSED') return 'neutral';
  return 'danger';
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 px-4 py-3">
      <span className="shrink-0 text-xs font-medium uppercase tracking-wide text-surface-400">
        {label}
      </span>
      <span className="min-w-0 break-words text-right text-sm text-surface-800">{value}</span>
    </div>
  );
}

export function TransactionDetailPage() {
  const { transactionId } = useParams<{ transactionId: string }>();

  const fetcher = async (): Promise<WalletTransaction> => {
    if (!transactionId) throw new Error('Missing transaction id.');
    return walletService.transaction(transactionId);
  };

  const { data, isLoading, error, retry } = useDashboardData<WalletTransaction>(fetcher, {
    deps: [transactionId],
  });

  if (isLoading) {
    return (
      <PageContainer title="Transaction">
        <Card>
          <div className="space-y-3 p-4">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="h-8 animate-pulse rounded-lg bg-surface-200/70" aria-hidden />
            ))}
          </div>
        </Card>
      </PageContainer>
    );
  }

  if (error || !data) {
    return (
      <PageContainer title="Transaction">
        <Card>
          <ErrorState
            message={error ?? 'Transaction not found.'}
            onRetry={retry}
          />
        </Card>
      </PageContainer>
    );
  }

  const isCredit = data.direction === 'CREDIT';
  const reference =
    data.reference_type && data.reference_type in REFERENCE_LINKS
      ? REFERENCE_LINKS[data.reference_type]
      : null;

  return (
    <PageContainer
      title="Transaction"
      subtitle={data.transaction_id}
      actions={
        <Link
          to="/transactions"
          className="inline-flex items-center gap-1.5 rounded-xl border border-surface-200 bg-surface-50 px-3 py-2 text-xs font-semibold text-surface-700 transition-colors hover:bg-surface-100"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          Back to history
        </Link>
      }
    >
      <div className="space-y-4">
        {/* Amount hero */}
        <Card>
          <div className="flex flex-col items-center gap-2 px-4 py-6 text-center">
            <span
              className={cn(
                'inline-flex h-12 w-12 items-center justify-center rounded-2xl',
                isCredit ? 'bg-brand-500/10 text-brand-400' : 'bg-surface-100 text-surface-600',
              )}
            >
              {isCredit ? (
                <ArrowDownLeft className="h-5 w-5" aria-hidden />
              ) : (
                <ArrowUpRight className="h-5 w-5" aria-hidden />
              )}
            </span>
            <p
              className={cn(
                'font-display text-3xl font-bold tabular-nums',
                isCredit ? 'text-brand-400' : 'text-surface-800',
              )}
            >
              {isCredit ? '+' : '−'}
              {formatUsdt(data.amount)} USDT
            </p>
            <Badge tone={statusTone(data.status)}>{data.status.toLowerCase()}</Badge>
          </div>
        </Card>

        {/* §25 field set — exactly what the ledger serializer exposes. */}
        <Card>
          <div className="divide-y divide-surface-200">
            <DetailRow
              label="Type"
              value={TYPE_LABELS[data.type] ?? data.type}
            />
            <DetailRow
              label="Direction"
              value={isCredit ? 'Credit (in)' : 'Debit (out)'}
            />
            <DetailRow
              label="Balance"
              value={data.balance_type.charAt(0) + data.balance_type.slice(1).toLowerCase()}
            />
            <DetailRow label="Status" value={<Badge tone={statusTone(data.status)}>{data.status.toLowerCase()}</Badge>} />
            <DetailRow label="Description" value={data.description || '—'} />
            <DetailRow
              label="Date"
              value={<span className="tabular-nums">{formatDateTime(data.created_at)}</span>}
            />
            <DetailRow
              label="Reference"
              value={
                data.reference_type
                  ? `${data.reference_type}${data.reference_id ? ` · ${data.reference_id}` : ''}`
                  : '—'
              }
            />
          </div>
        </Card>

        {reference && (
          <Link
            to={reference.to}
            className="flex items-center justify-between rounded-xl border border-surface-200 bg-surface-50 px-4 py-3 text-sm font-semibold text-brand-400 transition-colors hover:bg-brand-500/10"
          >
            {reference.label}
            <ArrowUpRight className="h-4 w-4" aria-hidden />
          </Link>
        )}

        <p className="text-center text-[11px] leading-relaxed text-surface-400">
          Transactions are recorded in the platform ledger.
        </p>
      </div>
    </PageContainer>
  );
}
