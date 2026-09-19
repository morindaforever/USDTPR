import { ArrowDownToLine, ArrowUpFromLine, Crown, HelpCircle, Info, Users } from 'lucide-react';
import { Link } from 'react-router-dom';

const ACTIONS = [
  { to: '/deposit', icon: ArrowUpFromLine, label: 'Deposit' },
  { to: '/withdraw', icon: ArrowDownToLine, label: 'Withdraw' },
  { to: '/vip', icon: Crown, label: 'VIP' },
  { to: '/team', icon: Users, label: 'Invite' },
  { to: '/about', icon: Info, label: 'About' },
  { to: '/help', icon: HelpCircle, label: 'Help' },
] as const;

/** Six dashboard shortcuts; destinations may still be placeholder pages. */
export function QuickActions() {
  return (
    <section aria-labelledby="quick-actions-heading">
      <h2 id="quick-actions-heading" className="mb-3 text-sm font-semibold text-surface-900">
        Quick actions
      </h2>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {ACTIONS.map(({ icon: Icon, label, to }) => (
          <Link
            key={label}
            to={to}
            className="group flex flex-col items-center gap-2 rounded-2xl border border-surface-200 bg-white px-3 py-4 text-center shadow-sm transition-all hover:-translate-y-0.5 hover:border-brand-200 hover:shadow-card"
          >
            <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 transition-colors group-hover:bg-brand-100">
              <Icon className="h-5 w-5" aria-hidden />
            </span>
            <span className="text-sm font-semibold text-surface-900">{label}</span>
          </Link>
        ))}
      </div>
    </section>
  );
}
