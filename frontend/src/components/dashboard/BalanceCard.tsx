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

/** Primary balance hero — pure display; balances come from the backend. */
export function BalanceCard({ summary, isLoading, error, onRetry }: BalanceCardProps) {
  const [hidden, setHidden] = useState(false);

  if (isLoading) {
    return (
      <div className="rounded-2xl border border-surface-200 bg-surface-50 p-6 shadow-card">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="mt-4 h-10 w-48" />
        <div className="mt-6 grid grid-cols-3 gap-3">
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
          <Skeleton className="h-16 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-surface-200 bg-surface-50 p-6 text-center shadow-card"
      >
        <p className="text-sm text-surface-500">Unable to load balance.</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 rounded-xl border border-surface-300 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-200"
        >
          Retry
        </button>
      </div>
    );
  }

  const display = (value: string) => (hidden ? '••••••' : formatUsdt(value));

  return (
    <section
      aria-label="Wallet balance"
      className="relative overflow-hidden rounded-2xl border border-surface-200 bg-surface-50 p-6 shadow-card"
    >
      <div
        aria-hidden
        className="bg-grid pointer-events-none absolute inset-0 opacity-60"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute -right-20 -top-24 h-64 w-64 rounded-full bg-brand-500/10 blur-3xl"
      />

      <div className="relative">
        <div className="flex items-center justify-between">
          <p className="eyebrow">Total balance</p>
          <button
            type="button"
            onClick={() => setHidden((h) => !h)}
            aria-label={hidden ? 'Show balance' : 'Hide balance'}
            className="rounded-lg p-1.5 text-surface-500 transition-colors hover:bg-surface-200 hover:text-surface-700"
          >
            {hidden ? <EyeOff className="h-4 w-4" aria-hidden /> : <Eye className="h-4 w-4" aria-hidden />}
          </button>
        </div>

        <div className="mt-2 flex items-baseline gap-2.5">
          <span className="figure text-4xl text-surface-800 md:text-[2.75rem] md:leading-[1.1]">
            {display(summary.total_balance)}
          </span>
          <span className="text-sm font-semibold text-brand-400">USDT</span>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <div className="rounded-xl border border-surface-200 bg-surface-900/60 px-4 py-3">
            <p className="text-[11px] font-medium uppercase tracking-wide text-surface-500">Deposit</p>
            <p className="figure mt-1 text-lg text-surface-700">{display(summary.deposit_balance)}</p>
          </div>
          <div className="rounded-xl border border-brand-500/20 bg-brand-500/5 px-4 py-3">
            <p className="text-[11px] font-medium uppercase tracking-wide text-brand-400/80">Withdrawable</p>
            <p className="figure mt-1 text-lg text-brand-400">{display(summary.withdrawable_balance)}</p>
          </div>
          <div className="rounded-xl border border-surface-200 bg-surface-900/60 px-4 py-3">
            <p className="text-[11px] font-medium uppercase tracking-wide text-surface-500">Pending</p>
            <p className="figure mt-1 text-lg text-surface-700">{display(summary.pending_balance)}</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-2.5">
          <Link
            to="/deposit"
            className="flex h-11 items-center justify-center gap-2 rounded-xl bg-brand-500 text-sm font-semibold text-white shadow-glow transition-colors hover:bg-brand-400"
          >
            <ArrowDownToLine className="h-4 w-4" aria-hidden />
            Deposit
          </Link>
          <Link
            to="/withdraw"
            className="flex h-11 items-center justify-center gap-2 rounded-xl border border-surface-300 bg-transparent text-sm font-semibold text-surface-700 transition-colors hover:border-surface-400 hover:bg-surface-100"
          >
            <ArrowUpFromLine className="h-4 w-4" aria-hidden />
            Withdraw
          </Link>
        </div>
      </div>
    </section>
  );
}
