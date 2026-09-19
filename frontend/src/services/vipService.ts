import { apiGet, apiPost } from './api';
import type {
  ApiEnvelope,
  CurrentPlan,
  PlanPurchaseSummary,
  PurchaseResponse,
  VipPlan,
  VipPurchase,
  VipReward,
} from '@/types';

/**
 * VIP services (Section 7). All financial values are Decimal strings from
 * the backend; the frontend never computes authoritative amounts.
 */
export const vipService = {
  /** Active plans — public endpoint. */
  async plans(): Promise<VipPlan[]> {
    const envelope = await apiGet<ApiEnvelope<VipPlan[]>>('/vip/plans/');
    return envelope.data ?? [];
  },

  /** One active plan's details — public endpoint. */
  async plan(planId: number): Promise<VipPlan> {
    const envelope = await apiGet<ApiEnvelope<VipPlan>>(`/vip/plans/${planId}/`);
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Plan not found.');
    }
    return envelope.data;
  },

  /** Server-computed confirmation data: balances for the purchase modal. */
  async planSummary(planId: number): Promise<PlanPurchaseSummary> {
    const envelope = await apiGet<ApiEnvelope<PlanPurchaseSummary>>(
      `/vip/plans/${planId}/summary/`,
    );
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to load plan details.');
    }
    return envelope.data;
  },

  /**
   * Purchase a plan. `idempotencyKey` must be unique per purchase attempt;
   * retrying with the same key can never debit twice.
   */
  async purchase(planId: number, idempotencyKey: string): Promise<ApiEnvelope<PurchaseResponse>> {
    return apiPost<ApiEnvelope<PurchaseResponse>>('/vip/purchase/', {
      plan_id: planId,
      idempotency_key: idempotencyKey,
    });
  },

  /** The user's active purchases. */
  async active(): Promise<VipPurchase[]> {
    const envelope = await apiGet<ApiEnvelope<VipPurchase[]>>('/vip/active/');
    return envelope.data ?? [];
  },

  /** Full purchase history, newest first. */
  async purchases(): Promise<VipPurchase[]> {
    const envelope = await apiGet<ApiEnvelope<VipPurchase[]>>('/vip/purchases/');
    return envelope.data ?? [];
  },

  /** Section 4 dashboard compatibility helper. */
  async currentPlan(): Promise<CurrentPlan | null> {
    const envelope = await apiGet<ApiEnvelope<CurrentPlan | null>>('/vip/current/');
    return envelope.data ?? null;
  },

  /** Reward history, newest cycle first (Section 8). */
  async rewards(): Promise<VipReward[]> {
    const envelope = await apiGet<ApiEnvelope<VipReward[]>>('/vip/rewards/');
    return envelope.data ?? [];
  },

  /** One reward — owner-only (404 for anyone else, per IDOR convention). */
  async reward(rewardId: string): Promise<VipReward> {
    const envelope = await apiGet<ApiEnvelope<VipReward>>(`/vip/rewards/${rewardId}/`);
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Reward not found.');
    }
    return envelope.data;
  },
};
