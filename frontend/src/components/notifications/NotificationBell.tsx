import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell } from 'lucide-react';
import { notificationService } from '@/services/notificationService';
import { cn } from '@/utils/cn';

/**
 * Header notification bell (Section 13 §29). The unread count always comes
 * from GET /api/notifications/unread-count/ — never hardcoded.
 * Refreshes on mount, on route activity, and on a slow 60s interval (§30:
 * no aggressive polling, no WebSockets). Silently shows nothing on error.
 */
export function NotificationBell() {
  const [unread, setUnread] = useState(0);

  const refresh = useCallback(() => {
    notificationService
      .unreadCount()
      .then(setUnread)
      .catch(() => setUnread(0));
  }, []);

  useEffect(() => {
    refresh();
    // Route changes re-render the Header; refresh when the location changes.
    const onPop = () => refresh();
    window.addEventListener('popstate', onPop);
    const interval = window.setInterval(refresh, 60_000);
    return () => {
      window.removeEventListener('popstate', onPop);
      window.clearInterval(interval);
    };
  }, [refresh]);

  return (
    <Link
      to="/notifications"
      aria-label={
        unread > 0
          ? `Notifications — ${unread} unread`
          : 'Notifications — all read'
      }
      className={cn(
        'relative rounded-lg p-2 text-surface-500 transition-colors',
        'hover:bg-surface-100 hover:text-surface-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-600',
      )}
    >
      <Bell className="h-5 w-5" aria-hidden />
      {unread > 0 && (
        <span
          aria-hidden
          className={cn(
            'absolute -right-0.5 -top-0.5 min-w-[1.1rem] rounded-full bg-accent-500 px-1 text-center',
            'text-[10px] font-bold leading-[1.1rem] text-white ring-2 ring-white',
          )}
        >
          {unread > 99 ? '99+' : unread}
        </span>
      )}
    </Link>
  );
}
