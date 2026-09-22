import { Crown, Gauge, UserRound, Users, Wallet } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/utils/cn';

const ITEMS = [
  { to: '/home', label: 'Home', icon: Gauge, end: true },
  { to: '/vip', label: 'VIP', icon: Crown, end: true },
  { to: '/wallet', label: 'Wallet', icon: Wallet, end: true },
  { to: '/team', label: 'Team', icon: Users, end: true },
  { to: '/account', label: 'Account', icon: UserRound, end: true },
] as const;

/**
 * Thumb-friendly bottom navigation for the mobile dashboard.
 * Hidden on `lg+` where the sidebar takes over.
 */
export function BottomNavigation() {
  return (
    <nav
      aria-label="Bottom navigation"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-surface-200 bg-surface-900/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden"
    >
      <div className="mx-auto grid max-w-2xl grid-cols-5">
        {ITEMS.map(({ to, label, icon: Icon, ...rest }) => (
          <NavLink
            key={to}
            to={to}
            end={'end' in rest ? rest.end : true}
            className={({ isActive }) =>
              cn(
                'flex flex-col items-center gap-0.5 py-2.5 text-[10px] font-medium transition-colors',
                isActive ? 'text-brand-400' : 'text-surface-500 hover:text-surface-600',
              )
            }
          >
            {({ isActive }) => (
              <>
                <span
                  className={cn(
                    'flex h-7 w-12 items-center justify-center rounded-full transition-colors',
                    isActive && 'bg-brand-500/15',
                  )}
                >
                  <Icon
                    className={cn('h-5 w-5 transition-transform', isActive && 'scale-105')}
                    strokeWidth={isActive ? 2.2 : 1.8}
                    aria-hidden
                  />
                </span>
                <span aria-current={isActive ? 'page' : undefined}>{label}</span>
              </>
            )}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
