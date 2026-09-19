import { apiGet } from './api';
import type {
  ApiEnvelope,
  PaginatedEnvelope,
  ReferralCommission,
  ReferralSummary,
  TeamMember,
} from '@/types';

/**
 * Referral/team services (Section 9). All figures — counts, commission
 * amounts, rates, the shareable link — are backend-computed; the frontend
 * never derives authoritative referral data.
 */
export const referralService = {
  /** Summary: code, link, team counts, commission totals (§32). */
  async summary(): Promise<ReferralSummary> {
    const envelope = await apiGet<ApiEnvelope<ReferralSummary>>('/referrals/summary/');
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to load referral summary.');
    }
    return envelope.data;
  },

  /** Direct (level 1) referrals. */
  async direct(): Promise<TeamMember[]> {
    const envelope = await apiGet<ApiEnvelope<TeamMember[]>>('/referrals/direct/');
    return envelope.data ?? [];
  },

  /** Paginated team list with backend level/status/search filters (§30, §51). */
  async team(params: { level?: number; status?: string; search?: string; page?: number } = {}) {
    const query = new URLSearchParams();
    if (params.level) query.set('level', String(params.level));
    if (params.status) query.set('status', params.status);
    if (params.search) query.set('search', params.search);
    if (params.page) query.set('page', String(params.page));
    const qs = query.toString();
    return apiGet<PaginatedEnvelope<TeamMember>>(`/referrals/team/${qs ? `?${qs}` : ''}`);
  },

  /** Paginated commission history with backend filters (§33). */
  async commissions(params: { level?: number; status?: string; page?: number } = {}) {
    const query = new URLSearchParams();
    if (params.level) query.set('level', String(params.level));
    if (params.status) query.set('status', params.status);
    if (params.page) query.set('page', String(params.page));
    const qs = query.toString();
    return apiGet<PaginatedEnvelope<ReferralCommission>>(`/referrals/commissions/${qs ? `?${qs}` : ''}`);
  },

  /** One commission — owner-only (§34). */
  async commission(commissionId: string): Promise<ReferralCommission> {
    const envelope = await apiGet<ApiEnvelope<ReferralCommission>>(
      `/referrals/commissions/${commissionId}/`,
    );
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Commission not found.');
    }
    return envelope.data;
  },
};
