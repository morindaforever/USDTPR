import { LogOut } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { NotificationBell } from '@/components/notifications';
import { useAuth } from '@/context/AuthContext';

/**
 * Slim top bar for the authenticated dashboard. Carries brand + notifications
 * + sign-out on mobile; on desktop the sidebar owns navigation and this bar
 * stays minimal (brand + quick actions).
 */
export function Header() {
  const { logout, currentUser } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  return (
    <header className="sticky top-0 z-30 border-b border-surface-200 bg-surface-950/85 backdrop-blur lg:hidden">
      <div className="flex h-14 w-full items-center justify-between px-4">
        <Link to="/home" className="flex items-center gap-2" aria-label="NexusUSDT home">
          <Logo className="h-8 w-8" />
          <span className="font-display text-base font-bold tracking-tight text-surface-800">
            Nexus<span className="text-brand-400">USDT</span>
          </span>
        </Link>

        <div className="flex items-center gap-1">
          <NotificationBell />
          <button
            type="button"
            aria-label={`Sign out${currentUser ? ` (${currentUser.full_name || currentUser.email})` : ''}`}
            onClick={handleLogout}
            className="rounded-lg p-2 text-surface-500 transition-colors hover:bg-surface-200 hover:text-surface-700"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
