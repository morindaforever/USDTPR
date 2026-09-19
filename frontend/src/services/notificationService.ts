import { apiGet, apiPost } from './api';
import type {
  AppNotification,
  NotificationFilters,
  PaginatedEnvelope,
} from '@/types';

/**
 * Notification services (Section 13). The unread count is NEVER hardcoded —
 * it always comes from GET /api/notifications/unread-count/ (§29).
 */

function toQueryString(filters: NotificationFilters): string {
  const params = new URLSearchParams();
  if (filters.type) params.set('type', filters.type);
  if (filters.is_read !== undefined && filters.is_read !== '') {
    params.set('is_read', String(filters.is_read));
  }
  if (filters.page) params.set('page', String(filters.page));
  if (filters.page_size) params.set('page_size', String(filters.page_size));
  const query = params.toString();
  return query ? `?${query}` : '';
}

export interface UnreadCountEnvelope {
  success: boolean;
  message: string;
  data: { unread_count: number };
}

export const notificationService = {
  async list(
    filters: NotificationFilters = {},
  ): Promise<PaginatedEnvelope<AppNotification> & { unread_count?: number }> {
    return apiGet<PaginatedEnvelope<AppNotification> & { unread_count?: number }>(
      `/notifications/${toQueryString(filters)}`,
    );
  },

  async unreadCount(): Promise<number> {
    const body = await apiGet<UnreadCountEnvelope>('/notifications/unread-count/');
    // apiGet returns the raw body; the count lives inside `data` (§29).
    const maybeEnvelope = body as unknown as UnreadCountEnvelope & { unread_count?: number };
    return maybeEnvelope.data?.unread_count ?? maybeEnvelope.unread_count ?? 0;
  },

  async markRead(notificationId: number): Promise<AppNotification> {
    const body = await apiPost<{ data?: AppNotification } & Partial<AppNotification>>(
      `/notifications/${notificationId}/read/`,
    );
    return body.data ?? (body as unknown as AppNotification);
  },

  async markAllRead(): Promise<{ marked: number; unread_count: number }> {
    const body = await apiPost<{ data?: { marked: number; unread_count: number } }>(
      '/notifications/read-all/',
    );
    return (
      body.data ?? { marked: 0, unread_count: 0 }
    );
  },
};
