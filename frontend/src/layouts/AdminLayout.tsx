import { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  BarChart3,
  Bell,
  FileClock,
  Landmark,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  MapPin,
  Menu,
  Crown,
  RefreshCcw,
  Settings,
  Share2,
  Users,
  Wallet,
  X,
} from 'lucide-react';
import { cn } from '@/utils/cn';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/Spinner';

const NAV_ITEMS = [
  { to: '/admin', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/admin/users', label: 'Users', icon: Users },
  { to: '/admin/deposits', label: 'Deposits', icon: Landmark },
  { to: '/admin/deposit-addresses', label: 'Deposit Addresses', icon: MapPin },
  { to: '/admin/withdrawals', label: 'Withdrawals', icon: Wallet },
  { to: '/admin/vip-plans', label: 'VIP Plans', icon: Crown },
  { to: '/admin/vip-purchases', label: 'VIP Purchases', icon: BarChart3 },
  { to: '/admin/rewards', label: 'Rewards', icon: RefreshCcw },
  { to: '/admin/referrals', label: 'Referrals', icon: Share2 },
  { to: '/admin/commissions', label: 'Commissions', icon: BarChart3 },
  { to: '/admin/support', label: 'Support', icon: LifeBuoy },
  { to: '/admin/transactions', label: 'Transactions', icon: Wallet },
  { to: '/admin/notifications', label: 'Notifications', icon: Bell },
  { to: '/admin/audit-logs', label: 'Audit Logs', icon: FileClock },
  { to: '/admin/settings', label: 'Settings', icon: Settings },
];

/**
 * Admin layout (Section 12 §4–6). Renders only for staff users — the
 * backend still enforces every permission on every API call; this guard is
 * presentation only (§3).
 */
export default function AdminLayout() {
  const { currentUser, logout, isLoading } = useAuth();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!isLoading && !currentUser) navigate('/login', { replace: true });
  }, [isLoading, currentUser, navigate]);

  if (isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-surface-950">
        <Spinner size="lg" label="Loading admin" />
      </div>
    );
  }
  if (!currentUser) return null;

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  };

  return (
    <div className="min-h-dvh bg-surface-950 text-surface-100">
      {/* Admin header (§6) */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-surface-50/90 backdrop-blur">
        <div className="flex h-14 items-center justify-between gap-3 px-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="rounded-lg p-2 text-surface-300 hover:bg-surface-200/40 lg:hidden"
              onClick={() => setDrawerOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <span className="font-display text-base font-bold">
              Nexus<span className="text-brand-400">USDT</span>
              <span className="ml-2 rounded-md bg-brand-600/20 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-brand-300">
                Admin
              </span>
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="hidden text-xs text-surface-400 sm:block">
              {currentUser.full_name || currentUser.email}
            </span>
            <button
              type="button"
              onClick={() => navigate('/home')}
              className="rounded-lg px-2.5 py-1.5 text-xs font-semibold text-surface-300 hover:bg-surface-200/40"
            >
              User site
            </button>
            <button
              type="button"
              onClick={() => void handleLogout()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-surface-200/40 px-3 py-1.5 text-xs font-semibold text-surface-200 hover:bg-surface-200/40"
            >
              <LogOut className="h-3.5 w-3.5" aria-hidden />
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="flex">
        {/* Desktop sidebar (§5) */}
        <aside className="sticky top-14 hidden h-[calc(100dvh-3.5rem)] w-56 shrink-0 overflow-y-auto border-r border-white/10 bg-surface-50/60 lg:block">
          <nav className="space-y-0.5 p-3" aria-label="Admin sections">
            {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-brand-500/15 text-brand-400'
                      : 'text-surface-300 hover:bg-surface-200/40 hover:text-white',
                  )
                }
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden />
                {label}
              </NavLink>
            ))}
          </nav>
        </aside>

        {/* Mobile drawer (§4, §74) */}
        {drawerOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            <button
              type="button"
              aria-label="Close navigation"
              className="absolute inset-0 bg-black/60 backdrop-blur-sm"
              onClick={() => setDrawerOpen(false)}
            />
            <div className="relative h-full w-64 overflow-y-auto border-r border-white/10 bg-surface-50 p-3">
              <div className="mb-3 flex items-center justify-between px-2">
                <span className="text-sm font-bold text-white">Admin</span>
                <button
                  type="button"
                  onClick={() => setDrawerOpen(false)}
                  className="rounded-lg p-1.5 text-surface-400 hover:bg-surface-200/40"
                  aria-label="Close"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <nav className="space-y-0.5" aria-label="Admin sections">
                {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={end}
                    onClick={() => setDrawerOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium',
                        isActive ? 'bg-brand-500/15 text-brand-400' : 'text-surface-300 hover:bg-surface-200/40',
                      )
                    }
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden />
                    {label}
                  </NavLink>
                ))}
              </nav>
            </div>
          </div>
        )}

        {/* Content */}
        <main className="min-w-0 flex-1 px-4 py-6 md:px-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
