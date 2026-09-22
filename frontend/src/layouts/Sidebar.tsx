import {
  ArrowDownToLine,
  ArrowUpFromLine,
  Crown,
  Gauge,
  LifeBuoy,
  LogOut,
  ReceiptText,
  Settings,
  Sparkles,
  UserRound,
  Users,
  Wallet,
} from 'lucide-react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { NotificationBell } from '@/components/notifications';
import { useAuth } from '@/context/AuthContext';
import { cn } from '@/utils/cn';
import type { LucideIcon } from 'lucide-react';

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const MAIN_NAV: NavItem[] = [
  { to: '/home', label: 'Dashboard', icon: Gauge, end: true },
  { to: '/wallet', label: 'Wallet', icon: Wallet, end: true },
  { to: '/deposit', label: 'Deposit', icon: ArrowDownToLine, end: true },
  { to: '/withdraw', label: 'Withdraw', icon: ArrowUpFromLine, end: true },
  { to: '/transactions', label: 'Transactions', icon: ReceiptText, end: true },
  { to: '/vip', label: 'VIP Plans', icon: Crown, end: true },
  { to: '/team', label: 'Team', icon: Users, end: true },
];

const SECONDARY_NAV: NavItem[] = [
  { to: '/account', label: 'Profile', icon: UserRound, end: true },
  { to: '/support', label: 'Support', icon: LifeBuoy, end: true },
];

function SidebarLink({ item, onNavigate }: { item: NavItem; onNavigate?: () => void }) {
  const { icon: Icon } = item;
  return (
    <NavLink
      to={item.to}
      end={item.end}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'group relative flex items-center gap-3 rounded-xl px-3 py-2 text-[13px] font-medium transition-colors duration-150',
          isActive
            ? 'bg-surface-100 text-surface-800'
            : 'text-surface-500 hover:bg-surface-100/60 hover:text-surface-700',
        )
      }
    >
      {({ isActive }) => (
        <>
          {/* Active rail */}
          <span
            aria-hidden
            className={cn(
              'absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-brand-400 transition-opacity',
              isActive ? 'opacity-100' : 'opacity-0',
            )}
          />
          <Icon
            className={cn(
              'h-[18px] w-[18px] shrink-0 transition-colors',
              isActive ? 'text-brand-400' : 'text-surface-500 group-hover:text-surface-600',
            )}
            strokeWidth={isActive ? 2.2 : 1.8}
            aria-hidden
          />
          <span className="truncate">{item.label}</span>
        </>
      )}
    </NavLink>
  );
}

/**
 * Desktop application sidebar — the primary navigation for the authenticated
 * product. Hidden below `lg`; mobile uses the bottom tab bar instead.
 */
export function Sidebar() {
  const { currentUser, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  const displayName = currentUser?.full_name || currentUser?.email || 'Account';

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-surface-200 bg-surface-900 lg:flex">
      {/* Brand */}
      <div className="flex h-16 shrink-0 items-center gap-2.5 border-b border-surface-200 px-5">
        <Link to="/home" className="flex items-center gap-2.5" aria-label="NexusUSDT home">
          <Logo className="h-8 w-8" />
          <span className="font-display text-[15px] font-bold tracking-tight text-surface-800">
            Nexus<span className="text-brand-400">USDT</span>
          </span>
        </Link>
      </div>

      {/* Primary nav */}
      <nav aria-label="Primary" className="flex-1 overflow-y-auto px-3 py-4">
        <p className="eyebrow px-3 pb-2">Platform</p>
        <div className="space-y-0.5">
          {MAIN_NAV.map((item) => (
            <SidebarLink key={item.to} item={item} />
          ))}
        </div>

        <p className="eyebrow px-3 pb-2 pt-6">Account</p>
        <div className="space-y-0.5">
          {SECONDARY_NAV.map((item) => (
            <SidebarLink key={item.to} item={item} />
          ))}
        </div>
      </nav>

      {/* Lower sidebar: notifications / account / logout */}
      <div className="shrink-0 border-t border-surface-200 p-3">
        <div className="flex items-center gap-2 rounded-xl bg-surface-100/70 p-2.5">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-brand-500/15 text-brand-400">
            <Sparkles className="h-4 w-4" aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-[13px] font-semibold text-surface-700">{displayName}</p>
            <p className="truncate text-[11px] text-surface-500">
              {currentUser?.email ?? 'Signed in'}
            </p>
          </div>
          <NotificationBell />
        </div>
        <div className="mt-2 flex items-center gap-1">
          <Link
            to="/account"
            className="flex flex-1 items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-surface-500 transition-colors hover:bg-surface-100/60 hover:text-surface-700"
          >
            <Settings className="h-4 w-4" aria-hidden />
            Settings
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            aria-label={`Sign out${currentUser ? ` (${displayName})` : ''}`}
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-[13px] font-medium text-surface-500 transition-colors hover:bg-danger-500/10 hover:text-danger-600"
          >
            <LogOut className="h-4 w-4" aria-hidden />
            Sign out
          </button>
        </div>
      </div>
    </aside>
  );
}
