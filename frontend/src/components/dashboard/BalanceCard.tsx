import { useState } from 'react';
import { ArrowDownToLine, ArrowUpFromLine, Eye, EyeOff } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Skeleton } from '@/hooks';
import { formatUsdt } from '@/utils/format';
import type { WalletSummary } from '@/types';

interface BalanceCardProps {
  summary: WalletSummary | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}

/** Primary balance card — pure display; balances come from the backend. */
export function BalanceCard({ summary, isLoading, error, onRetry }: BalanceCardProps) {
  const [hidden, setHidden] = useState(false);

  if (isLoading) {
    return (
      <div className="rounded-2xl bg-surface-950 p-5 shadow-card">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-3 h-9 w-44" />
        <div className="mt-5 grid grid-cols-2 gap-3">
          <Skeleton className="h-11 rounded-xl" />
          <Skeleton className="h-11 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="rounded-2xl bg-surface-950 p-5 text-center shadow-card">
        <p className="text-sm text-surface-300">Unable to load balance.</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-500"
        >
          Retry
        </button>
      </div>
    );
  }

  const display = (value: string) => (hidden ? '••••••' : formatUsdt(value));

  return (
    <div className="relative overflow-hidden rounded-2xl bg-surface-950 p-5 text-white shadow-card">
      <div
        aria-hidden
        className="absolute inset-0 opacity-40"
        style={{
          background: 'radial-gradient(320px 160px at 85% -10%, rgba(35,166,125,0.45), transparent)',
        }}
      />
      <div className="relative">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wide text-surface-400">Total balance</p>
          <button
            type="button"
            onClick={() => setHidden((h) => !h)}
            aria-label={hidden ? 'Show balance' : 'Hide balance'}
            className="rounded-lg p-1.5 text-surface-400 transition-colors hover:bg-white/10 hover:text-white"
          >
            {hidden ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
          </button>
        </div>
        <div className="mt-1 flex items-baseline gap-2">
          <span className="font-display text-3xl font-bold tabular-nums">{display(summary.total_balance)}</span>
          <span className="text-sm font-semibold text-surface-400">USDT</span>
        </div>

        <dl className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
            <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-400">Deposit</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">{display(summary.deposit_balance)}</dd>
          </div>
          <div className="rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
            <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-400">Withdrawable</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">{display(summary.withdrawable_balance)}</dd>
          </div>
          <div className="col-span-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
            <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-400">Pending</dt>
            <dd className="mt-0.5 font-semibold tabular-nums">{display(summary.pending_balance)}</dd>
          </div>
        </dl>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <Link
            to="/deposit"
            className="flex items-center justify-center gap-1.5 rounded-xl bg-brand-600 px-3 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-500"
          >
            <ArrowUpFromLine className="h-4 w-4" aria-hidden />
            Deposit
          </Link>
          <Link
            to="/withdraw"
            className="flex items-center justify-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-white/10"
          >
            <ArrowDownToLine className="h-4 w-4" aria-hidden />
            Withdraw
          </Link>
        </div>
      </div>
    </div>
  );
}
