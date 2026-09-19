import { apiGet, apiPatch, apiPost } from './api';
import type { AuthUser } from './authService';
import type { AccountActivityEntry, ApiEnvelope } from '@/types';

/**
 * Account services (Section 11). The authenticated user always comes from
 * the server session — no identifier is ever sent from the client (§9).
 */
export const accountService = {
  /** GET /api/account/me/ — same safe shape as the auth endpoint (§50). */
  async me(): Promise<AuthUser> {
    const envelope = await apiGet<ApiEnvelope<{ user: AuthUser }>>('/account/me/');
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to load the account.');
    }
    return envelope.data.user;
  },

  /** PATCH /api/account/profile/ — full_name and/or phone only (§7–8). */
  async updateProfile(payload: { full_name?: string; phone?: string }): Promise<AuthUser> {
    const envelope = await apiPatch<ApiEnvelope<{ user: AuthUser }>>('/account/profile/', payload);
    if (!envelope.success || !envelope.data) {
      const detail = envelope.errors
        ? Object.values(envelope.errors).flat().join(' ')
        : envelope.message;
      throw new Error(detail || 'Unable to update the profile.');
    }
    return envelope.data.user;
  },

  /**
   * POST /api/account/change-password/ (§14). The backend invalidates all
   * refresh tokens on success; the caller should re-authenticate.
   */
  async changePassword(payload: {
    current_password: string;
    new_password: string;
    confirm_password: string;
  }): Promise<ApiEnvelope<null>> {
    return apiPost<ApiEnvelope<null>>('/account/change-password/', payload);
  },

  /** GET /api/account/activity/ — safe curated feed (§19). */
  async activity(): Promise<AccountActivityEntry[]> {
    const envelope = await apiGet<ApiEnvelope<{ results: AccountActivityEntry[] }>>(
      '/account/activity/',
    );
    return envelope.data?.results ?? [];
  },
};
