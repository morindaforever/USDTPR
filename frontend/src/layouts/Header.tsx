import { LogOut } from 'lucide-react';
import { Link, NavLink, useNavigate } from 'react-router-dom';
import { cn } from '@/utils/cn';
import { Logo } from '@/components/Logo';
import { NotificationBell } from '@/components/notifications';
import { useAuth } from '@/context/AuthContext';

const NAV_ITEMS = [
  { to: '/home', label: 'Home' },
  { to: '/vip', label: 'VIP' },
  { to: '/team', label: 'Team' },
  { to: '/account', label: 'Account' },
];

/**
 * Top bar for the authenticated dashboard. Mobile relies on the bottom
 * navigation; desktop shows inline links here instead.
 */
export function Header() {
  const { logout, currentUser } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="sticky top-0 z-40 border-b border-surface-200/70 bg-white/85 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-3xl items-center justify-between px-4 md:px-6">
        <Link to="/home" className="flex items-center gap-2" aria-label="NexusUSDT home">
          <Logo className="h-8 w-8" />
          <span className="font-display text-base font-bold tracking-tight text-surface-900">
            Nexus<span className="text-brand-600">USDT</span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Primary">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                cn(
                  'rounded-lg px-3 py-1.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-brand-50 text-brand-700'
                    : 'text-surface-600 hover:bg-surface-100 hover:text-surface-900',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-1">
          {/* §29: live unread badge from GET /api/notifications/unread-count/. */}
          <NotificationBell />
          <button
            type="button"
            aria-label={`Sign out${currentUser ? ` (${currentUser.full_name || currentUser.email})` : ''}`}
            onClick={handleLogout}
            className="rounded-lg p-2 text-surface-500 transition-colors hover:bg-surface-100 hover:text-surface-800"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
