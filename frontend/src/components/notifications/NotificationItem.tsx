import {
  ArrowDownLeft,
  ArrowUpRight,
  Bell,
  Crown,
  Gift,
  LifeBuoy,
  Megaphone,
  RefreshCcw,
  Settings,
  ShieldCheck,
  Users,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { formatDateTime } from '@/utils/format';
import type { AppNotification } from '@/types';

/** Icons + accents per notification type (§3) — color never carries meaning alone. */
const TYPE_META: Record<string, { icon: typeof Bell; classes: string; label: string }> = {
  DEPOSIT: { icon: ArrowDownLeft, classes: 'bg-brand-500/10 text-brand-400', label: 'Deposit' },
  WITHDRAWAL: { icon: ArrowUpRight, classes: 'bg-surface-100 text-surface-700', label: 'Withdrawal' },
  VIP: { icon: Crown, classes: 'bg-accent-200 text-accent-700', label: 'VIP' },
  REWARD: { icon: Gift, classes: 'bg-violet-50 text-violet-700', label: 'Reward' },
  REFERRAL: { icon: Users, classes: 'bg-info-50 text-info-700', label: 'Referral' },
  SUPPORT: { icon: LifeBuoy, classes: 'bg-blue-50 text-blue-700', label: 'Support' },
  SECURITY: { icon: ShieldCheck, classes: 'bg-rose-50 text-rose-700', label: 'Security' },
  ANNOUNCEMENT: { icon: Megaphone, classes: 'bg-brand-500/12 text-brand-400', label: 'Announcement' },
  SYSTEM: { icon: Settings, classes: 'bg-surface-100 text-surface-600', label: 'System' },
};

function metaFor(type: string) {
  return TYPE_META[type] ?? { icon: Bell, classes: 'bg-surface-100 text-surface-600', label: type };
}

/** §36: relative time for recent items, absolute in the tooltip. */
function relativeTime(iso: string): string {
  const then = new Date(iso).getTime();
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return formatDateTime(iso);
}

interface NotificationItemProps {
  notification: AppNotification;
  onMarkRead: (id: number) => void;
  busy?: boolean;
}

/** One notification row; unread rows get a dot + bolder text (§5). */
export function NotificationItem({ notification, onMarkRead, busy }: NotificationItemProps) {
  const { icon: Icon, classes, label } = metaFor(notification.type);

  const body = (
    <div className="flex items-start gap-3 px-4 py-3">
      <span
        aria-hidden
        className={cn(
          'inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-xl',
          classes,
        )}
      >
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <p
            className={cn(
              'truncate text-sm text-surface-800',
              notification.is_read ? 'font-medium' : 'font-semibold',
            )}
          >
            {notification.title}
          </p>
          {!notification.is_read && (
            <span className="h-2 w-2 shrink-0 rounded-full bg-accent-500" aria-label="Unread" />
          )}
        </div>
        <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-surface-500">
          {notification.message}
        </p>
        <p className="mt-1 text-[11px] text-surface-400" title={formatDateTime(notification.created_at)}>
          {relativeTime(notification.created_at)} · {label}
        </p>
      </div>
      {!notification.is_read && (
        <button
          type="button"
          disabled={busy}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onMarkRead(notification.id);
          }}
          className="shrink-0 rounded-lg border border-surface-200 px-2 py-1 text-[11px] font-semibold text-surface-600 transition-colors hover:bg-surface-100 disabled:opacity-50"
        >
          Mark read
        </button>
      )}
    </div>
  );

  return (
    <li className={cn('relative', !notification.is_read && 'bg-brand-50/40')}>
      {body}
    </li>
  );
}

/** Filter chips shown above the list (§3). */
export function NotificationFilters({
  value,
  onChange,
}: {
  value: string;
  onChange: (next: string) => void;
}) {
  const OPTIONS = [
    { value: '', label: 'All' },
    { value: 'unread', label: 'Unread' },
    { value: 'DEPOSIT', label: 'Deposits' },
    { value: 'WITHDRAWAL', label: 'Withdrawals' },
    { value: 'REWARD', label: 'Rewards' },
    { value: 'VIP', label: 'VIP' },
    { value: 'REFERRAL', label: 'Referrals' },
    { value: 'SUPPORT', label: 'Support' },
  ] as const;

  return (
    <div role="group" aria-label="Filter notifications" className="flex flex-wrap gap-2">
      {OPTIONS.map((opt) => (
        <button
          key={opt.value || 'all'}
          type="button"
          aria-pressed={value === opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors',
            value === opt.value
              ? 'border-brand-600 bg-brand-600 text-surface-800'
              : 'border-surface-200 bg-surface-50 text-surface-600 hover:bg-surface-100',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

/** §37: honest empty state. */
export function NotificationEmptyState() {
  return (
    <div className="px-4 py-12 text-center">
      <span className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-surface-100 text-surface-400">
        <Bell className="h-6 w-6" aria-hidden />
      </span>
      <p className="mt-3 text-sm font-semibold text-surface-800">You're all caught up.</p>
      <p className="mt-1 text-xs text-surface-500">No notifications to show.</p>
    </div>
  );
}

/** §35: loading skeleton rows. */
export function NotificationSkeleton() {
  return (
    <ul className="divide-y divide-surface-200">
      {[0, 1, 2].map((i) => (
        <li key={i} className="flex items-start gap-3 px-4 py-3">
          <span className="h-9 w-9 shrink-0 animate-pulse rounded-xl bg-surface-200/70" aria-hidden />
          <div className="flex-1 space-y-2">
            <span className="block h-3 w-1/2 animate-pulse rounded bg-surface-200/70" aria-hidden />
            <span className="block h-3 w-3/4 animate-pulse rounded bg-surface-200/70" aria-hidden />
          </div>
        </li>
      ))}
    </ul>
  );
}

export { RefreshCcw };
