import { ArrowDownToLine, ArrowUpFromLine, Crown, LifeBuoy, Users } from 'lucide-react';
import { Link } from 'react-router-dom';

const ACTIONS = [
  { to: '/deposit', icon: ArrowDownToLine, label: 'Deposit' },
  { to: '/withdraw', icon: ArrowUpFromLine, label: 'Withdraw' },
  { to: '/vip', icon: Crown, label: 'VIP Plans' },
  { to: '/team', icon: Users, label: 'Team' },
  { to: '/help', icon: LifeBuoy, label: 'Help' },
] as const;

/** Dashboard shortcuts. */
export function QuickActions() {
  return (
    <section aria-labelledby="quick-actions-heading">
      <h2 id="quick-actions-heading" className="eyebrow mb-3">
        Quick actions
      </h2>
      <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
        {ACTIONS.map(({ icon: Icon, label, to }) => (
          <Link
            key={label}
            to={to}
            className="group flex items-center gap-3 rounded-xl border border-surface-200 bg-surface-50 px-4 py-3.5 transition-colors hover:border-brand-500/30 hover:bg-surface-100"
          >
            <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-500/12 text-brand-400 transition-colors group-hover:bg-brand-500/20">
              <Icon className="h-[18px] w-[18px]" aria-hidden />
            </span>
            <span className="truncate text-sm font-semibold text-surface-700">{label}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
