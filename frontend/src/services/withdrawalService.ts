import { apiGet, apiPost } from './api';
import type {
  ApiEnvelope,
  PaginatedEnvelope,
  Withdrawal,
  WithdrawalDetail,
  WithdrawalNetwork,
  WithdrawalQuote,
  WithdrawalRules,
  WithdrawalSummary,
} from '@/types';

/**
 * Withdrawal services (Section 10). The backend is authoritative for every
 * financial figure — balances, minimum, fee, net — and for all status
 * transitions; the frontend only displays what the API returns.
 */
export const withdrawalService = {
  /** Active networks with format hints (§7, §45). */
  async networks(): Promise<WithdrawalNetwork[]> {
    const envelope = await apiGet<ApiEnvelope<WithdrawalNetwork[]>>('/withdrawals/networks/');
    return envelope.data ?? [];
  },

  /** Public rules: minimum and fee configuration (§46). */
  async rules(): Promise<WithdrawalRules> {
    const envelope = await apiGet<ApiEnvelope<WithdrawalRules>>('/withdrawals/rules/');
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to load withdrawal rules.');
    }
    return envelope.data;
  },

  /** Backend-computed balances for the /withdraw page (§41). */
  async summary(): Promise<WithdrawalSummary> {
    const envelope = await apiGet<ApiEnvelope<WithdrawalSummary>>('/withdrawals/summary/');
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to load balances.');
    }
    return envelope.data;
  },

  /**
   * Informational fee/net quote (§47). The final submission always
   * recalculates server-side; a stale quote can never change the outcome.
   */
  async quote(amount: string, network?: string): Promise<WithdrawalQuote> {
    const envelope = await apiPost<ApiEnvelope<WithdrawalQuote>>('/withdrawals/quote/', {
      amount,
      ...(network ? { network } : {}),
    });
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to calculate the fee.');
    }
    return envelope.data;
  },

  /**
   * Submit a withdrawal. `idempotencyKey` makes retries safe: the same key
   * can never create two withdrawals or lock funds twice (§35).
   */
  async create(payload: {
    network: string;
    destination_address: string;
    amount: string;
    idempotency_key: string;
  }): Promise<ApiEnvelope<WithdrawalDetail>> {
    return apiPost<ApiEnvelope<WithdrawalDetail>>('/withdrawals/', payload);
  },

  /** Paginated history, newest first; destination masked (§38, §40). */
  async list(page = 1): Promise<PaginatedEnvelope<Withdrawal>> {
    return apiGet<PaginatedEnvelope<Withdrawal>>(`/withdrawals/?page=${page}`);
  },

  /** Owner-only detail with the full destination address (§39). */
  async detail(withdrawalId: string): Promise<WithdrawalDetail> {
    const envelope = await apiGet<ApiEnvelope<WithdrawalDetail>>(
      `/withdrawals/${withdrawalId}/`,
    );
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to load the withdrawal.');
    }
    return envelope.data;
  },
};
