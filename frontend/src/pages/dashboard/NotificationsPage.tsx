import { useCallback, useState } from 'react';
import { CheckCheck, ChevronLeft, ChevronRight } from 'lucide-react';
import { Card, ErrorState, PageContainer } from '@/components';
import {
  NotificationEmptyState,
  NotificationFilters,
  NotificationItem,
  NotificationSkeleton,
} from '@/components/notifications';
import { useDashboardData } from '@/hooks';
import { notificationService } from '@/services/notificationService';
import type { AppNotification, PaginationMeta } from '@/types';

const PAGE_SIZE = 15;

interface ListState {
  rows: AppNotification[];
  pagination: PaginationMeta | null;
  unread: number;
}

/**
 * Notification center (Section 13 §2–3, §6–7). Server-side filtering and
 * pagination — the browser never loads the whole collection. Every action
 * (mark read, mark all) is idempotent on the backend (§5); the list
 * refetches after each action so counts stay honest.
 */
export function NotificationsPage() {
  const [filter, setFilter] = useState('');
  const [page, setPage] = useState(1);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [markingAll, setMarkingAll] = useState(false);

  const fetcher = useCallback(async (): Promise<ListState> => {
    const filters =
      filter === 'unread' ? { is_read: false as const } : filter ? { type: filter } : {};
    const payload = await notificationService.list({
      ...filters,
      page,
      page_size: PAGE_SIZE,
    });
    return {
      rows: payload.data ?? [],
      pagination: payload.pagination ?? null,
      unread: payload.unread_count ?? 0,
    };
  }, [filter, page]);

  const { data, isLoading, error, retry } = useDashboardData<ListState>(fetcher, {
    deps: [filter, page],
  });

  const markRead = useCallback(
    async (id: number) => {
      setBusyId(id);
      try {
        await notificationService.markRead(id);
        retry(); // refetch rows + unread count
      } finally {
        setBusyId(null);
      }
    },
    [retry],
  );

  const markAllRead = useCallback(async () => {
    setMarkingAll(true);
    try {
      await notificationService.markAllRead();
      retry();
    } finally {
      setMarkingAll(false);
    }
  }, [retry]);

  const changeFilter = (next: string) => {
    setFilter(next);
    setPage(1);
  };

  const pagination = data?.pagination ?? null;

  return (
    <PageContainer
      title="Notifications"
      subtitle="Updates about your account, wallet, and rewards."
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <NotificationFilters value={filter} onChange={changeFilter} />
          <button
            type="button"
            onClick={() => void markAllRead()}
            disabled={markingAll || (data?.unread ?? 0) === 0}
            className="inline-flex items-center gap-1.5 rounded-xl border border-surface-200 bg-white px-3 py-2 text-xs font-semibold text-surface-700 transition-colors hover:bg-surface-50 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <CheckCheck className="h-4 w-4" aria-hidden />
            Mark all read
          </button>
        </div>

        <Card>
          {isLoading ? (
            <NotificationSkeleton />
          ) : error ? (
            <ErrorState message={error} onRetry={retry} />
          ) : !data || data.rows.length === 0 ? (
            <NotificationEmptyState />
          ) : (
            <ul className="divide-y divide-surface-100">
              {data.rows.map((row) => (
                <NotificationItem
                  key={row.id}
                  notification={row}
                  onMarkRead={(id) => void markRead(id)}
                  busy={busyId === row.id || markingAll}
                />
              ))}
            </ul>
          )}

          {pagination && pagination.pages > 1 && !isLoading && !error && (
            <div className="flex items-center justify-between border-t border-surface-100 px-4 py-3">
              <button
                type="button"
                disabled={pagination.page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-xs font-semibold text-surface-700 transition-colors hover:bg-surface-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <ChevronLeft className="h-3.5 w-3.5" aria-hidden />
                Prev
              </button>
              <span className="text-xs text-surface-500">
                Page {pagination.page} of {pagination.pages} · {pagination.count} total
              </span>
              <button
                type="button"
                disabled={pagination.page >= pagination.pages}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex items-center gap-1 rounded-lg border border-surface-200 px-3 py-1.5 text-xs font-semibold text-surface-700 transition-colors hover:bg-surface-50 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" aria-hidden />
              </button>
            </div>
          )}
        </Card>

        {data && data.unread > 0 && (
          <p className="text-center text-xs text-surface-500">
            {data.unread} unread notification{data.unread === 1 ? '' : 's'}
          </p>
        )}
      </div>
    </PageContainer>
  );
}
