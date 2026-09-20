import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Crown, Info, RefreshCw } from 'lucide-react';
import { formatUsdt } from '@/utils/format';
import { PageContainer } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { vipService } from '@/services/vipService';
import {
  ActiveVipCard,
  PurchaseConfirmModal,
  VipPlanCard,
  VipPurchaseHistory,
  VipRewardHistory,
} from '@/components/vip';
import type { PlanPurchaseSummary, PurchaseResponse, VipPlan, VipPurchase, VipReward } from '@/types';

/**
 * VIP plans page (Sections 7–8): browse plans, purchase using the combined
 * deposit + withdrawable balance, view active plans with backend-computed
 * reward progress, reward history, and purchase history. Nothing here
 * credits rewards — that is the backend engine's job.
 */
export function VipPage() {
  const navigate = useNavigate();

  const [selectedPlan, setSelectedPlan] = useState<VipPlan | null>(null);
  const [summary, setSummary] = useState<PlanPurchaseSummary | null>(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [purchasing, setPurchasing] = useState(false);
  const [purchaseError, setPurchaseError] = useState<string | null>(null);
  const [success, setSuccess] = useState<PurchaseResponse | null>(null);

  const plansQuery = useDashboardData<VipPlan[]>(() => vipService.plans());
  const activeQuery = useDashboardData<VipPurchase[]>(() => vipService.active());
  const historyQuery = useDashboardData<VipPurchase[]>(() => vipService.purchases());
  const rewardsQuery = useDashboardData<VipReward[]>(() => vipService.rewards());

  const heldPlanIds = useMemo(
    () => new Set((activeQuery.data ?? []).map((p) => p.plan_name)),
    [activeQuery.data],
  );

  // Server-computed confirmation data whenever a plan is selected.
  useEffect(() => {
    if (!selectedPlan) {
      setSummary(null);
      return;
    }
    let cancelled = false;
    setSummaryLoading(true);
    setPurchaseError(null);
    vipService
      .planSummary(selectedPlan.id)
      .then((data) => {
        if (!cancelled) setSummary(data);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setSummary(null);
          setPurchaseError(err instanceof Error ? err.message : 'Unable to load plan details.');
        }
      })
      .finally(() => {
        if (!cancelled) setSummaryLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedPlan]);

  const confirmPurchase = useCallback(async () => {
    if (!selectedPlan || purchasing) return;
    setPurchasing(true);
    setPurchaseError(null);
    try {
      const idempotencyKey = `web-${selectedPlan.id}-${crypto.randomUUID()}`;
      const envelope = await vipService.purchase(selectedPlan.id, idempotencyKey);
      if (!envelope.success || !envelope.data) {
        setPurchaseError(envelope.message || 'Unable to complete the purchase.');
        return;
      }
      setSuccess(envelope.data);
      setSelectedPlan(null);
      activeQuery.retry();
      historyQuery.retry();
      rewardsQuery.retry();
    } catch (err: unknown) {
      setPurchaseError(
        err instanceof Error ? err.message : 'Unable to complete the purchase. Please try again.',
      );
    } finally {
      setPurchasing(false);
    }
  }, [selectedPlan, purchasing, activeQuery, historyQuery]);

  const plans = plansQuery.data ?? [];

  return (
    <PageContainer title="VIP Plans" subtitle="Choose a plan that matches your available balance.">
      <div className="space-y-6">
        {/* Notice — plans are configuration terms */}
        <div className="flex gap-3 rounded-xl bg-sky-50 p-3.5 text-sky-900 ring-1 ring-inset ring-sky-200">
          <Info className="mt-0.5 h-5 w-5 shrink-0" aria-hidden />
          <div className="text-sm">
            <p className="font-semibold">VIP Plans</p>
            <p className="mt-0.5 opacity-90">
              VIP plans shown here are platform configurations. Returns are based on plan terms.
            </p>
          </div>
        </div>

        {/* Success screen */}
        {success && (
          <section className="rounded-2xl border border-brand-200 bg-white p-5 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
              <Crown className="h-6 w-6" aria-hidden />
            </div>
            <h2 className="mt-3 text-lg font-semibold text-surface-900">VIP Plan Activated</h2>
            <p className="mt-1 text-sm text-surface-500">
              {success.purchase.plan_name} is now active. Your first reward will be
              credited by the daily reward run.
            </p>
            <dl className="mx-auto mt-4 grid max-w-xs grid-cols-2 gap-3 text-sm">
              <div className="rounded-xl bg-surface-50 p-3 text-left">
                <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
                  Investment
                </dt>
                <dd className="mt-0.5 font-semibold tabular-nums text-surface-900">
                  {Number(success.purchase.investment_amount) === 0
                    ? 'Free'
                    : `${formatUsdt(success.purchase.investment_amount)} USDT`}
                </dd>
              </div>
              <div className="rounded-xl bg-surface-50 p-3 text-left">
                <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
                  Target
                </dt>
                <dd className="mt-0.5 font-semibold tabular-nums text-surface-900">
                  {formatUsdt(success.purchase.target_amount)} USDT
                </dd>
              </div>
              <div className="rounded-xl bg-surface-50 p-3 text-left">
                <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
                  Daily rate
                </dt>
                <dd className="mt-0.5 font-semibold tabular-nums text-surface-900">
                  {success.purchase.daily_rate_percent}%
                </dd>
              </div>
              <div className="rounded-xl bg-surface-50 p-3 text-left">
                <dt className="text-[11px] font-medium uppercase tracking-wide text-surface-500">
                  Purchase ID
                </dt>
                <dd className="mt-0.5 truncate font-mono text-xs font-semibold text-surface-900">
                  {success.purchase.purchase_id}
                </dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-surface-500">
              Remaining spendable balance (deposit + withdrawable): {formatUsdt(success.remaining_balance)} USDT
            </p>
            <div className="mt-4 flex gap-3">
              <button
                type="button"
                onClick={() => setSuccess(null)}
                className="flex-1 rounded-xl border border-surface-200 px-4 py-2.5 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
              >
                View My VIP
              </button>
              <button
                type="button"
                onClick={() => navigate('/home')}
                className="flex-1 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700"
              >
                Go to Dashboard
              </button>
            </div>
          </section>
        )}

        {/* Active plans */}
        <section aria-labelledby="active-vip-heading">
          <h2 id="active-vip-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Active Plans
          </h2>
          {activeQuery.isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-36 w-full" />
            </div>
          ) : activeQuery.error ? (
            <div className="rounded-2xl border border-surface-200 bg-white p-5 text-center">
              <p className="flex items-center justify-center gap-2 text-sm text-surface-600">
                <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden />
                Unable to load your active plans.
              </p>
              <button
                type="button"
                onClick={activeQuery.retry}
                className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-surface-200 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
              >
                <RefreshCw className="h-4 w-4" aria-hidden /> Retry
              </button>
            </div>
          ) : (activeQuery.data ?? []).length === 0 ? (
            <p className="rounded-2xl border border-dashed border-surface-200 p-5 text-center text-sm text-surface-500">
              No active VIP plans. Choose a plan below to get started.
            </p>
          ) : (
            <div className="space-y-3">
              {(activeQuery.data ?? []).map((purchase) => (
                <ActiveVipCard key={purchase.purchase_id} purchase={purchase} />
              ))}
            </div>
          )}
        </section>

        {/* Plan grid */}
        <section aria-labelledby="plans-heading">
          <h2 id="plans-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Available Plans
          </h2>
          {plansQuery.isLoading ? (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-64 w-full rounded-2xl" />
              ))}
            </div>
          ) : plansQuery.error ? (
            <div className="rounded-2xl border border-surface-200 bg-white p-5 text-center">
              <p className="flex items-center justify-center gap-2 text-sm text-surface-600">
                <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden />
                Unable to load VIP plans.
              </p>
              <button
                type="button"
                onClick={plansQuery.retry}
                className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-surface-200 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
              >
                <RefreshCw className="h-4 w-4" aria-hidden /> Retry
              </button>
            </div>
          ) : plans.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-surface-200 p-5 text-center text-sm text-surface-500">
              No active VIP plans right now. Please check back later.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {plans.map((plan) => (
                <VipPlanCard
                  key={plan.id}
                  plan={plan}
                  alreadyHeld={heldPlanIds.has(plan.name)}
                  onSelect={(selected) => {
                    setSuccess(null);
                    setSelectedPlan(selected);
                  }}
                />
              ))}
            </div>
          )}
        </section>

        {/* Reward history (Section 8) */}
        <section aria-labelledby="reward-history-heading">
          <h2 id="reward-history-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Reward History
          </h2>
          {rewardsQuery.isLoading ? (
            <div className="space-y-2.5">
              <Skeleton className="h-16 w-full rounded-2xl" />
              <Skeleton className="h-16 w-full rounded-2xl" />
            </div>
          ) : rewardsQuery.error ? (
            <div className="rounded-2xl border border-surface-200 bg-white p-5 text-center">
              <p className="flex items-center justify-center gap-2 text-sm text-surface-600">
                <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden />
                Unable to load reward history.
              </p>
              <button
                type="button"
                onClick={rewardsQuery.retry}
                className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-surface-200 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
              >
                <RefreshCw className="h-4 w-4" aria-hidden /> Retry
              </button>
            </div>
          ) : (
            <VipRewardHistory rewards={rewardsQuery.data ?? []} />
          )}
        </section>

        {/* Purchase history */}
        <section aria-labelledby="vip-history-heading">
          <h2 id="vip-history-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Purchase History
          </h2>
          {historyQuery.isLoading ? (
            <div className="space-y-2.5">
              <Skeleton className="h-16 w-full rounded-2xl" />
              <Skeleton className="h-16 w-full rounded-2xl" />
            </div>
          ) : historyQuery.error ? (
            <p className="rounded-2xl border border-surface-200 bg-white p-5 text-center text-sm text-surface-600">
              Unable to load purchase history.
            </p>
          ) : (
            <VipPurchaseHistory purchases={historyQuery.data ?? []} />
          )}
        </section>
      </div>

      <PurchaseConfirmModal
        open={selectedPlan !== null}
        summary={summary}
        isLoading={summaryLoading}
        isPurchasing={purchasing}
        errorMessage={purchaseError}
        onConfirm={confirmPurchase}
        onClose={() => {
          if (!purchasing) setSelectedPlan(null);
        }}
      />
    </PageContainer>
  );
}
