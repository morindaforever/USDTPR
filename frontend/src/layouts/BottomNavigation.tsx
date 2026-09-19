import { Crown, Home, User, Users } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/utils/cn';

const ITEMS = [
  { to: '/home', label: 'Home', icon: Home },
  { to: '/vip', label: 'VIP', icon: Crown },
  { to: '/team', label: 'Team', icon: Users },
  { to: '/account', label: 'Account', icon: User },
] as const;

/**
 * Thumb-friendly bottom navigation for the mobile dashboard.
 * Hidden on `md+` where the header links take over.
 */
export function BottomNavigation() {
  return (
    <nav
      aria-label="Bottom navigation"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-surface-200/70 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
    >
      <div className="mx-auto grid max-w-3xl grid-cols-4">
        {ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex flex-col items-center gap-0.5 py-2.5 text-[11px] font-medium transition-colors',
                isActive ? 'text-brand-600' : 'text-surface-400 hover:text-surface-600',
              )
            }
          >
            {({ isActive }) => (
              <>
                <Icon
                  className={cn('h-5 w-5 transition-transform', isActive && 'scale-110')}
                  strokeWidth={isActive ? 2.4 : 2}
                  aria-hidden
                />
                <span aria-current={isActive ? 'page' : undefined}>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
