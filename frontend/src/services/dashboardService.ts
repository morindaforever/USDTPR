import { apiGet } from './api';
import type {
  ApiEnvelope,
  WalletSummary,
} from '@/types';

/**
 * Read-only dashboard data services. Every call here hits an
 * authentication-required backend endpoint; the backend identifies the user
 * from the token — no user ids are ever sent or trusted.
 */

export const walletService = {
  async summary(): Promise<WalletSummary> {
    const envelope = await apiGet<ApiEnvelope<WalletSummary>>('/wallet/summary/');
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to load wallet information.');
    }
    return envelope.data;
  },
};

// vipService moved to vipService.ts (Section 7) — see services/index.ts.
// The dashboard shows only real ledger data.

export const siteService = {
  /** Public platform flags (§37): maintenance switch lives in the admin
   * panel; this endpoint only exposes the resulting boolean. */
  async status(): Promise<{ maintenance: boolean }> {
    const envelope = await apiGet<ApiEnvelope<{ maintenance: boolean }>>('/site/status/');
    return envelope.data ?? { maintenance: false };
  },
};
