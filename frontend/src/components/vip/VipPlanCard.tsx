import { Crown, Sparkles } from 'lucide-react';
import { Badge } from '@/components';
import { formatUsdt } from '@/utils/format';
import type { VipPlan } from '@/types';

export interface VipPlanCardProps {
  plan: VipPlan;
  /** True when the user already holds this plan (e.g. welcome claim). */
  alreadyHeld?: boolean;
  onSelect: (plan: VipPlan) => void;
}

/** One VIP plan card: investment, target, daily rate, and entry point. */
export function VipPlanCard({ plan, alreadyHeld = false, onSelect }: VipPlanCardProps) {
  const isWelcome = plan.is_welcome_plan ?? plan.plan_number === 0;
  const investsNothing = Number(plan.investment_amount) === 0;

  return (
    <div className="flex h-full flex-col rounded-2xl border border-surface-200 bg-white p-5 transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between">
        <div
          className={`flex h-10 w-10 items-center justify-center rounded-xl ${
            isWelcome ? 'bg-accent-50 text-accent-600' : 'bg-brand-50 text-brand-600'
          }`}
        >
          {isWelcome ? (
            <Sparkles className="h-5 w-5" aria-hidden />
          ) : (
            <Crown className="h-5 w-5" aria-hidden />
          )}
        </div>
        <div className="flex gap-1.5">
          {isWelcome && <Badge tone="warning">Free</Badge>}
        </div>
      </div>

      <h3 className="mt-3 text-base font-semibold text-surface-900">{plan.name}</h3>
      <p className="mt-0.5 text-xs text-surface-500">
        {isWelcome ? 'Free plan' : `Plan ${plan.plan_number}`}
      </p>

      <dl className="mt-4 space-y-2.5 text-sm">
        <div className="flex items-center justify-between">
          <dt className="text-surface-500">Investment</dt>
          <dd className="font-semibold tabular-nums text-surface-900">
            {investsNothing ? 'Free — 0 USDT' : `${formatUsdt(plan.investment_amount)} USDT`}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-surface-500">{isWelcome ? 'Welcome Reward Target' : 'Target'}</dt>
          <dd className="font-semibold tabular-nums text-surface-900">
            {formatUsdt(plan.target_amount)} USDT
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-surface-500">Daily Return</dt>
          <dd className="font-semibold tabular-nums text-brand-700">{plan.daily_rate_percent}%</dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-surface-500">Daily Reward</dt>
          <dd className="font-semibold tabular-nums text-brand-700">
            {formatUsdt(
              (Number(plan.target_amount) * Number(plan.daily_rate)).toFixed(2),
            )}{' '}
            USDT
          </dd>
        </div>
        {isWelcome && (
          <p className="rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800">
            Promotional reward — accrues daily from the next reward cycle until the
            reward target is reached. Not investment profit. Does not unlock withdrawals.
          </p>
        )}
      </dl>

      <div className="mt-5 flex-1" />
      <button
        type="button"
        onClick={() => onSelect(plan)}
        disabled={alreadyHeld}
        className={`w-full rounded-xl px-4 py-2.5 text-sm font-semibold transition-colors ${
          alreadyHeld
            ? 'cursor-not-allowed bg-surface-100 text-surface-400'
            : 'bg-brand-600 text-white shadow-sm hover:bg-brand-700 active:bg-brand-800'
        }`}
      >
        {alreadyHeld ? 'Claimed' : isWelcome ? 'Claim Welcome Reward' : 'Purchase'}
      </button>
    </div>
  );
}
