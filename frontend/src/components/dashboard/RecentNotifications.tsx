import { Link } from 'react-router-dom';
import { Bell, ChevronRight } from 'lucide-react';
import { Card, ErrorState } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { notificationService } from '@/services/notificationService';
import { formatDateTime } from '@/utils/format';
import type { AppNotification } from '@/types';

/**
 * Dashboard "Recent Notifications" (Section 13 §28): latest 5 from the
 * existing notification list API. "View All" routes to /notifications.
 */
export function RecentNotifications() {
  const { data, isLoading, error, retry } = useDashboardData<{ rows: AppNotification[] }>(
    async () => {
      const payload = await notificationService.list({ page: 1, page_size: 5 });
      return { rows: payload.data ?? [] };
    },
  );

  const rows = data?.rows ?? [];

  return (
    <Card>
      <div className="p-5">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold text-surface-900">Recent Notifications</h2>
          <Link
            to="/notifications"
            className="inline-flex items-center gap-0.5 text-xs font-semibold text-brand-700 hover:text-brand-800"
          >
            View All
            <ChevronRight className="h-3.5 w-3.5" aria-hidden />
          </Link>
        </div>

        {isLoading ? (
          <div className="mt-4 space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-3">
                <Skeleton className="h-9 w-9 rounded-xl" />
                <div className="flex-1 space-y-1.5">
                  <Skeleton className="h-3 w-24" />
                  <Skeleton className="h-2.5 w-16" />
                </div>
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="mt-4">
            <ErrorState message={error} onRetry={retry} />
          </div>
        ) : rows.length === 0 ? (
          <p className="mt-4 text-xs text-surface-500">
            You're all caught up — no notifications to show.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-surface-100">
            {rows.map((row) => (
              <li key={row.id} className="flex items-start gap-3 py-2.5">
                <span
                  className={
                    row.is_read
                      ? 'mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-surface-100 text-surface-500'
                      : 'mt-0.5 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600'
                  }
                >
                  <Bell className="h-3.5 w-3.5" aria-hidden />
                </span>
                <div className="min-w-0 flex-1">
                  <p
                    className={
                      row.is_read
                        ? 'truncate text-sm text-surface-700'
                        : 'truncate text-sm font-semibold text-surface-900'
                    }
                  >
                    {row.title}
                  </p>
                  <p className="text-[11px] text-surface-400">{formatDateTime(row.created_at)}</p>
                </div>
                {!row.is_read && (
                  <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-accent-500" aria-label="Unread" />
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}
