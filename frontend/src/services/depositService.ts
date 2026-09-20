import { apiGet, apiPost, apiPostForm } from './api';
import type { ApiEnvelope, Deposit, DepositAddress, DepositNetwork } from '@/types';

/**
 * Deposit services (Section 6 API surface, wired in Section 15).
 * All financial values come from the backend — the UI never computes
 * minimums, statuses, or credits.
 */

export const depositService = {
  async networks(): Promise<DepositNetwork[]> {
    const envelope = await apiGet<ApiEnvelope<DepositNetwork[]>>('/deposits/networks/');
    return envelope.data ?? [];
  },

  async address(networkCode: string): Promise<DepositAddress> {
    const envelope = await apiGet<ApiEnvelope<DepositAddress>>(
      `/deposits/address/?network=${encodeURIComponent(networkCode)}`,
    );
    if (!envelope.data) throw new Error(envelope.message || 'No deposit address available.');
    return envelope.data;
  },

  async list(): Promise<Deposit[]> {
    const envelope = await apiGet<ApiEnvelope<Deposit[]>>('/deposits/');
    return envelope.data ?? [];
  },

  async minimum(): Promise<string> {
    // Minimum comes from the withdrawal-style rules surface of the deposit
    // service: the backend validates the true value at submit time either way.
    const envelope = await apiGet<ApiEnvelope<{ minimum_amount: string }>>('/deposits/rules/');
    return envelope.data?.minimum_amount ?? '1.00';
  },

  async submit(payload: {
    network: string;
    amount: string;
    tx_hash?: string;
    order_id?: string;
    /** Optional payment screenshot (validated server-side). */
    screenshot?: File | null;
  }): Promise<Deposit> {
    let envelope: ApiEnvelope<Deposit>;
    try {
      if (payload.screenshot) {
        const form = new FormData();
        form.append('network', payload.network);
        form.append('amount', payload.amount);
        form.append('tx_hash', payload.tx_hash ?? '');
        form.append('order_id', payload.order_id ?? '');
        form.append('screenshot', payload.screenshot);
        envelope = await apiPostForm<ApiEnvelope<Deposit>>('/deposits/', form);
      } else {
        envelope = await apiPost<ApiEnvelope<Deposit>>('/deposits/', {
          network: payload.network,
          amount: payload.amount,
          tx_hash: payload.tx_hash ?? '',
          order_id: payload.order_id ?? '',
        });
      }
    } catch (err) {
      // The axios interceptor normalizes failures into ApiError with the
      // full envelope on `detail` — surface per-field messages from it.
      const detail = (err as { detail?: { errors?: Record<string, string[]> } }).detail;
      const fieldErrors = detail?.errors;
      const message = err instanceof Error && err.message ? err.message : 'Deposit submission failed.';
      throw Object.assign(new Error(message), {
        fieldErrors: fieldErrors && Object.keys(fieldErrors).length > 0 ? fieldErrors : undefined,
      });
    }
    if (!envelope.success || !envelope.data) {
      throw Object.assign(new Error(envelope.message || 'Deposit submission failed.'), {
        fieldErrors: envelope.errors as Record<string, string[]> | undefined,
      });
    }
    return envelope.data;
  },
};
