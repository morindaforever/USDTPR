import { apiGet, apiPost } from './api';
import type {
  ApiEnvelope,
  PaginatedEnvelope,
  SupportConversation,
  SupportConversationDetail,
} from '@/types';

/**
 * Support services (Section 11 §51). All list responses are paginated and
 * server-filtered; the user never sees another account's conversations.
 */
export type SupportStatusFilter = 'ALL' | 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';

export const supportService = {
  /** GET /api/support/conversations/ — paginated, newest activity first. */
  async list(status: SupportStatusFilter = 'ALL', page = 1): Promise<PaginatedEnvelope<SupportConversation>> {
    const params = new URLSearchParams({ page: String(page) });
    if (status !== 'ALL') params.set('status', status);
    return apiGet<PaginatedEnvelope<SupportConversation>>(
      `/support/conversations/?${params.toString()}`,
    );
  },

  /** POST /api/support/conversations/ — creates thread + first message. */
  async create(payload: { subject: string; message: string }): Promise<ApiEnvelope<SupportConversationDetail>> {
    return apiPost<ApiEnvelope<SupportConversationDetail>>('/support/conversations/', payload);
  },

  /** GET /api/support/conversations/<id>/ — owner-only (404 otherwise). */
  async detail(conversationId: string): Promise<SupportConversationDetail> {
    const envelope = await apiGet<ApiEnvelope<SupportConversationDetail>>(
      `/support/conversations/${conversationId}/`,
    );
    if (!envelope.success || !envelope.data) {
      throw new Error(envelope.message || 'Unable to load the conversation.');
    }
    return envelope.data;
  },

  /** POST /api/support/conversations/<id>/messages/ (§35). */
  async sendMessage(conversationId: string, message: string): Promise<ApiEnvelope<SupportConversationDetail>> {
    return apiPost<ApiEnvelope<SupportConversationDetail>>(
      `/support/conversations/${conversationId}/messages/`,
      { message },
    );
  },

  /** POST /api/support/conversations/<id>/close/ — idempotent (§38). */
  async close(conversationId: string): Promise<ApiEnvelope<SupportConversationDetail>> {
    return apiPost<ApiEnvelope<SupportConversationDetail>>(
      `/support/conversations/${conversationId}/close/`,
    );
  },

  /** POST /api/support/conversations/<id>/reopen/ (§39). */
  async reopen(conversationId: string): Promise<ApiEnvelope<SupportConversationDetail>> {
    return apiPost<ApiEnvelope<SupportConversationDetail>>(
      `/support/conversations/${conversationId}/reopen/`,
    );
  },
};
