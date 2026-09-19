import { Card } from '@/components';
import { PageContainer } from '@/components/PageContainer';

const PRINCIPLES = [
  {
    title: 'Modular by design',
    body: 'Accounts, wallet, deposits, withdrawals, VIP, referrals, support, and notifications are separate Django apps with their own APIs — changes stay scoped.',
  },
  {
    title: 'Auditable money movement',
    body: 'Every balance change is designed to flow through recorded transactions with database-level consistency. Nothing mutates a balance silently.',
  },
  {
    title: 'Mobile-first interface',
    body: 'The UI is designed for the phone in your pocket first, then scales up to tablet and desktop with the same components.',
  },
];

const ROADMAP = [
  { phase: 'Section 1', title: 'Foundation', status: 'In progress', current: true },
  { phase: 'Section 2', title: 'Accounts & authentication', status: 'Planned', current: false },
  { phase: 'Section 3', title: 'Wallet & deposits', status: 'Planned', current: false },
  { phase: 'Later', title: 'Withdrawals, VIP, referrals, support', status: 'Planned', current: false },
];

/** Public "About / how it works" page with roadmap. */
export function AboutPage() {
  return (
    <PageContainer
      title="About NexusUSDT"
      subtitle="What this platform is, how it is built, and where it is going."
    >
      <div className="space-y-6">
        <Card>
          <div className="p-5">
            <h2 className="text-sm font-semibold text-surface-900">The short version</h2>
            <p className="mt-2 text-sm leading-relaxed text-surface-600">
              NexusUSDT is a web platform for managing a USDT-based account:
              depositing, joining VIP tiers, growing a referral team, and tracking
              everything from a mobile-first dashboard. It is a development
              project — features arrive in planned sections, and nothing here is
              financial advice or a promise of returns.
            </p>
          </div>
        </Card>

        <section aria-labelledby="principles-heading">
          <h2 id="principles-heading" className="mb-3 font-display text-lg font-bold text-surface-900">
            How it is built
          </h2>
          <div className="grid gap-4 sm:grid-cols-3">
            {PRINCIPLES.map((p) => (
              <Card key={p.title}>
                <div className="p-4">
                  <h3 className="text-sm font-semibold text-surface-900">{p.title}</h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-surface-500">{p.body}</p>
                </div>
              </Card>
            ))}
          </div>
        </section>

        <section aria-labelledby="roadmap-heading">
          <h2 id="roadmap-heading" className="mb-3 font-display text-lg font-bold text-surface-900">
            Build roadmap
          </h2>
          <Card>
            <ul className="divide-y divide-surface-100">
              {ROADMAP.map((item) => (
                <li key={item.phase} className="flex items-center justify-between gap-4 px-4 py-3.5">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-surface-400">
                      {item.phase}
                    </p>
                    <p className="mt-0.5 text-sm font-medium text-surface-900">{item.title}</p>
                  </div>
                  <span
                    className={
                      item.current
                        ? 'inline-flex rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-semibold text-brand-700 ring-1 ring-inset ring-brand-200'
                        : 'inline-flex rounded-full bg-surface-100 px-2.5 py-1 text-[11px] font-semibold text-surface-500 ring-1 ring-inset ring-surface-200'
                    }
                  >
                    {item.status}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      </div>
    </PageContainer>
  );
}
