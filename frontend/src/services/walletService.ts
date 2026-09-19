import { apiGet } from './api';
import type {
  PaginatedEnvelope,
  TransactionFilters,
  WalletSummary,
  WalletTransaction,
} from '@/types';

/**
 * Wallet services (Section 5). Read-only by design — balance mutations are
 * internal backend operations; the UI can never credit/debit via API.
 */

function toQueryString(filters: TransactionFilters): string {
  const params = new URLSearchParams();
  if (filters.type) params.set('type', filters.type);
  if (filters.status) params.set('status', filters.status);
  if (filters.direction) params.set('direction', filters.direction);
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.search) params.set('search', filters.search);
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));
  const query = params.toString();
  return query ? `?${query}` : '';
}

export const walletService = {
  async summary(): Promise<WalletSummary> {
    const envelope = await apiGet<WalletSummary & { success?: boolean }>('/wallet/summary/');
    // The summary endpoint wraps data in {success, message, data}; the
    // generic helper returns the body, so unwrap defensively here.
    const maybeEnvelope = envelope as unknown as { data?: WalletSummary };
    return maybeEnvelope.data ?? (envelope as unknown as WalletSummary);
  },

  async transactions(
    filters: TransactionFilters = {},
  ): Promise<PaginatedEnvelope<WalletTransaction>> {
    return apiGet<PaginatedEnvelope<WalletTransaction>>(
      `/wallet/transactions/${toQueryString(filters)}`,
    );
  },

  async transaction(transactionId: string): Promise<WalletTransaction> {
    const envelope = await apiGet<WalletTransaction & { data?: WalletTransaction }>(
      `/wallet/transactions/${encodeURIComponent(transactionId)}/`,
    );
    const maybeEnvelope = envelope as unknown as { data?: WalletTransaction };
    return maybeEnvelope.data ?? (envelope as unknown as WalletTransaction);
  },
};
