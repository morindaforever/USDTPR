import { apiGet, apiPatch, apiPost } from './api';
import type {
  ApiEnvelope,
  PaginatedEnvelope,
} from '@/types';
import type {
  AdminAuditLog,
  AdminCommissionRow,
  AdminDashboard,
  AdminDepositRow,
  AdminNotification,
  AdminReferralRow,
  AdminReward,
  AdminSetting,
  AdminSupportDetail,
  AdminSupportRow,
  AdminTransaction,
  AdminUserDetail,
  AdminUserRow,
  AdminVipPlan,
  AdminVipPurchase,
  AdminWithdrawalRow,
} from '@/types/admin';

type ListParams = Record<string, string | number | undefined>;

function qs(params: ListParams = {}): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') search.set(key, String(value));
  });
  const str = search.toString();
  return str ? `?${str}` : '';
}

/** Unwraps a paginated admin list response (data + pagination meta). */
async function list<T>(url: string): Promise<PaginatedEnvelope<T>> {
  return apiGet<PaginatedEnvelope<T>>(url);
}

/**
 * Admin panel API (Section 12). Every call hits /api/admin/* which the
 * backend guards with IsAdminUser (+ per-action group checks); the client
 * performs no authorization logic of its own.
 */
export const adminService = {
  // Dashboard ---------------------------------------------------------------
  dashboard(range = 'all', from?: string, to?: string): Promise<ApiEnvelope<AdminDashboard>> {
    return apiGet(`/admin/dashboard/${qs({ range, from, to })}`);
  },

  // Users -------------------------------------------------------------------
  users(params: ListParams): Promise<PaginatedEnvelope<AdminUserRow>> {
    return list(`/admin/users/${qs(params)}`);
  },
  user(userId: string): Promise<ApiEnvelope<AdminUserDetail>> {
    return apiGet(`/admin/users/${userId}/`);
  },
  userHistory(userId: string, type: string): Promise<ApiEnvelope<{ results: unknown[] }>> {
    return apiGet(`/admin/users/${userId}/history/${qs({ type })}`);
  },
  userStatus(userId: string, action: 'activate' | 'suspend' | 'ban', reason: string): Promise<ApiEnvelope<AdminUserDetail>> {
    return apiPost(`/admin/users/${userId}/status/`, { action, reason });
  },

  // Deposits ----------------------------------------------------------------
  deposits(params: ListParams): Promise<PaginatedEnvelope<AdminDepositRow>> {
    return list(`/admin/deposits/${qs(params)}`);
  },
  deposit(depositId: string): Promise<ApiEnvelope<{ deposit: AdminDepositRow }>> {
    return apiGet(`/admin/deposits/${depositId}/`);
  },
  depositAction(depositId: string, action: 'approve' | 'reject', reason = ''): Promise<ApiEnvelope<{ deposit: AdminDepositRow }>> {
    return apiPost(`/admin/deposits/${depositId}/${action}/`, { reason });
  },

  // Withdrawals ---------------------------------------------------------------
  withdrawals(params: ListParams): Promise<PaginatedEnvelope<AdminWithdrawalRow>> {
    return list(`/admin/withdrawals/${qs(params)}`);
  },
  withdrawal(withdrawalId: string): Promise<ApiEnvelope<{ withdrawal: AdminWithdrawalRow }>> {
    return apiGet(`/admin/withdrawals/${withdrawalId}/`);
  },
  withdrawalAction(
    withdrawalId: string,
    action: 'approve' | 'reject' | 'processing' | 'complete' | 'fail',
    payload: { reason?: string; transaction_hash?: string } = {},
  ): Promise<ApiEnvelope<{ withdrawal: AdminWithdrawalRow }>> {
    return apiPost(`/admin/withdrawals/${withdrawalId}/${action}/`, payload);
  },

  // VIP ----------------------------------------------------------------------
  vipPlans(): Promise<ApiEnvelope<{ results: AdminVipPlan[] }>> {
    return apiGet('/admin/vip-plans/');
  },
  createVipPlan(payload: Record<string, string | boolean>): Promise<ApiEnvelope<AdminVipPlan>> {
    return apiPost('/admin/vip-plans/', payload);
  },
  updateVipPlan(id: number, payload: Record<string, string | boolean>): Promise<ApiEnvelope<AdminVipPlan>> {
    return apiPatch(`/admin/vip-plans/${id}/`, payload);
  },
  vipPurchases(params: ListParams): Promise<PaginatedEnvelope<AdminVipPurchase>> {
    return list(`/admin/vip-purchases/${qs(params)}`);
  },

  // Rewards -------------------------------------------------------------------
  rewards(params: ListParams): Promise<PaginatedEnvelope<AdminReward>> {
    return list(`/admin/rewards/${qs(params)}`);
  },
  processRewards(cycleDate?: string): Promise<ApiEnvelope<{ result: Record<string, unknown> }>> {
    return apiPost('/admin/rewards/process/', cycleDate ? { cycle_date: cycleDate } : {});
  },
  retryReward(rewardId: string): Promise<ApiEnvelope<AdminReward>> {
    return apiPost(`/admin/rewards/${rewardId}/retry/`);
  },

  // Referrals & commissions ----------------------------------------------------
  referrals(params: ListParams): Promise<PaginatedEnvelope<AdminReferralRow>> {
    return list(`/admin/referrals/${qs(params)}`);
  },
  commissions(params: ListParams): Promise<PaginatedEnvelope<AdminCommissionRow>> {
    return list(`/admin/commissions/${qs(params)}`);
  },

  // Support ---------------------------------------------------------------------
  support(params: ListParams): Promise<PaginatedEnvelope<AdminSupportRow>> {
    return list(`/admin/support/${qs(params)}`);
  },
  supportConversation(conversationId: string): Promise<ApiEnvelope<AdminSupportDetail>> {
    return apiGet(`/admin/support/${conversationId}/`);
  },
  supportReply(conversationId: string, message: string): Promise<ApiEnvelope<AdminSupportDetail>> {
    return apiPost(`/admin/support/${conversationId}/messages/`, { message });
  },
  supportStatus(conversationId: string, status: string): Promise<ApiEnvelope<AdminSupportDetail>> {
    return apiPost(`/admin/support/${conversationId}/status/`, { status });
  },

  // Transactions -----------------------------------------------------------------
  transactions(params: ListParams): Promise<PaginatedEnvelope<AdminTransaction>> {
    return list(`/admin/transactions/${qs(params)}`);
  },

  // Notifications ------------------------------------------------------------------
  notifications(params: ListParams): Promise<PaginatedEnvelope<AdminNotification>> {
    return list(`/admin/notifications/${qs(params)}`);
  },
  broadcast(payload: { title: string; message: string; audience: string }): Promise<ApiEnvelope<{ delivered: number }>> {
    return apiPost('/admin/notifications/broadcast/', payload);
  },

  // Audit logs ------------------------------------------------------------------------
  auditLogs(params: ListParams): Promise<PaginatedEnvelope<AdminAuditLog>> {
    return list(`/admin/audit-logs/${qs(params)}`);
  },

  // Settings -----------------------------------------------------------------------------
  settings(group = 'all'): Promise<ApiEnvelope<{ results: AdminSetting[] }>> {
    return apiGet(`/admin/settings/${qs({ group })}`);
  },
  updateSetting(key: string, value: string): Promise<ApiEnvelope<AdminSetting>> {
    return apiPatch('/admin/settings/', { key, value });
  },
};
