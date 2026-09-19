import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BarChart3,
  Coins,
  Crown,
  Shield,
  Users,
  Zap,
} from 'lucide-react';
import { Button, Card } from '@/components';
import { fetchHealth } from '@/services/healthService';

const FEATURES = [
  {
    icon: Coins,
    title: 'USDT deposits',
    description:
      'Fund your account with USDT and track every transaction with full history.',
  },
  {
    icon: Crown,
    title: 'VIP tiers',
    description:
      'Unlock tiers with increasing benefits as you participate on the platform.',
  },
  {
    icon: Users,
    title: 'Team rewards',
    description:
      'Invite teammates and follow your referral network from a single dashboard.',
  },
  {
    icon: Shield,
    title: 'Auditable by design',
    description:
      'Every balance change is designed to be recorded and reviewable — no silent math.',
  },
  {
    icon: BarChart3,
    title: 'Clear reporting',
    description:
      'Deposits, withdrawals, and rewards organized in one clean activity view.',
  },
  {
    icon: Zap,
    title: 'Fast & mobile-first',
    description:
      'A responsive interface that feels native on your phone and scales to desktop.',
  },
];

const STEPS = [
  {
    step: '01',
    title: 'Create an account',
    description: 'Sign up with your email and secure it with a strong password.',
  },
  {
    step: '02',
    title: 'Fund your wallet',
    description: 'Deposit USDT and see it reflected in your balance.',
  },
  {
    step: '03',
    title: 'Grow with the platform',
    description: 'Join VIP tiers and build your team to unlock more benefits.',
  },
];

const FAQ = [
  {
    question: 'Is this a real investment platform?',
    answer:
      'NexusUSDT is a platform for exploring wallet, VIP, reward, referral, and transaction workflows.',
  },
  {
    question: 'How do deposits work?',
    answer:
      'Deposits are submitted for manual review by an administrator.',
  },
  {
    question: 'Are the rewards real income?',
    answer:
      'VIP rewards and referral commissions are calculated based on plan terms.',
  },
  {
    question: 'Can I withdraw money?',
    answer:
      'Withdrawal requests are reviewed and processed by the platform team.',
  },
];

/**
 * Landing page shell (Section 1). Hero, features, and how-it-works with
 * copy only — no return claims, no partnership claims.
 */
export function LandingPage() {
  const [apiStatus, setApiStatus] = useState<'checking' | 'online' | 'offline'>('checking');

  useEffect(() => {
    let cancelled = false;
    fetchHealth()
      .then(() => {
        if (!cancelled) setApiStatus('online');
      })
      .catch(() => {
        if (!cancelled) setApiStatus('offline');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="page-enter">
      {/* Hero */}
      <section className="relative overflow-hidden bg-surface-950">
        <div
          aria-hidden
          className="absolute inset-0 opacity-40"
          style={{
            background:
              'radial-gradient(600px 300px at 20% 0%, rgba(35,166,125,0.35), transparent), radial-gradient(500px 260px at 85% 20%, rgba(253,176,34,0.18), transparent)',
          }}
        />
        <div className="relative mx-auto w-full max-w-5xl px-4 py-16 text-center md:px-6 md:py-24">
          <div className="mx-auto mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs font-medium text-surface-200 backdrop-blur">
            <span
              className={
                apiStatus === 'online'
                  ? 'h-2 w-2 rounded-full bg-emerald-400'
                  : apiStatus === 'checking'
                    ? 'h-2 w-2 animate-pulse rounded-full bg-surface-400'
                    : 'h-2 w-2 rounded-full bg-red-400'
              }
            />
            {apiStatus === 'checking' && 'Connecting to API…'}
            {apiStatus === 'online' && 'Backend online'}
            {apiStatus === 'offline' && 'Backend offline (start the API)'}
          </div>

          <h1 className="font-display text-4xl font-extrabold leading-tight tracking-tight text-white md:text-6xl">
            Explore the USDT platform for{' '}
            <span className="bg-gradient-to-r from-brand-300 to-brand-500 bg-clip-text text-transparent">
              wallets, VIP tiers,
            </span>{' '}
            and team rewards
          </h1>
          <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-surface-300 md:text-lg">
            Explore wallet, VIP, reward, referral, and transaction workflows —
            mobile-first, with every balance change recorded in an auditable ledger.
          </p>

          <p className="mx-auto mt-4 inline-flex items-center gap-2 rounded-full border border-amber-300/30 bg-amber-400/10 px-3.5 py-1.5 text-xs font-bold uppercase tracking-wide text-amber-300">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" aria-hidden />
            Platform Overview
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link to="/signup">
              <Button size="lg" fullWidth className="sm:w-auto">
                Create free account
              </Button>
            </Link>
            <Link to="/about">
              <Button size="lg" variant="outline" fullWidth className="sm:w-auto">
                How it works
              </Button>
            </Link>
          </div>

          <dl className="mx-auto mt-12 grid max-w-2xl grid-cols-3 gap-3">
            {[
              ['24/7', 'Platform access'],
              ['USDT', 'Core currency'],
              ['3 tiers', 'VIP roadmap'],
            ].map(([value, label]) => (
              <div
                key={label}
                className="rounded-2xl border border-white/10 bg-white/5 px-3 py-4 backdrop-blur"
              >
                <dt className="sr-only">{label}</dt>
                <dd className="font-display text-lg font-bold text-white md:text-2xl">{value}</dd>
                <dd className="mt-0.5 text-[11px] text-surface-400 md:text-xs">{label}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>

      {/* Features */}
      <section className="mx-auto w-full max-w-5xl px-4 py-14 md:px-6 md:py-20">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-2xl font-bold text-surface-900 md:text-3xl">
            Everything in one dashboard
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-surface-500 md:text-base">
            Each capability below is a dedicated module with its own service,
            API, and audit trail — not bolted-on pages.
          </p>
        </div>

        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, description }) => (
            <Card key={title} className="group transition-shadow hover:shadow-card-hover">
              <div className="p-5">
                <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50 text-brand-600 transition-colors group-hover:bg-brand-100">
                  <Icon className="h-5 w-5" aria-hidden />
                </div>
                <h3 className="text-sm font-semibold text-surface-900">{title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-surface-500">{description}</p>
              </div>
            </Card>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="border-y border-surface-200/70 bg-white">
        <div className="mx-auto w-full max-w-5xl px-4 py-14 md:px-6 md:py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display text-2xl font-bold text-surface-900 md:text-3xl">
              Get started in three steps
            </h2>
            <p className="mt-3 text-sm text-surface-500 md:text-base">
              A straightforward path from signup to your first deposit.
            </p>
          </div>
          <ol className="mt-10 grid gap-4 md:grid-cols-3">
            {STEPS.map(({ step, title, description }) => (
              <li key={step}>
                <Card className="h-full">
                  <div className="p-5">
                    <span className="font-display text-sm font-bold text-brand-600">{step}</span>
                    <h3 className="mt-2 text-sm font-semibold text-surface-900">{title}</h3>
                    <p className="mt-1.5 text-sm leading-relaxed text-surface-500">{description}</p>
                  </div>
                </Card>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto w-full max-w-5xl px-4 py-14 md:px-6 md:py-20">
        <div className="relative overflow-hidden rounded-3xl bg-surface-950 px-6 py-12 text-center md:py-16">
          <div
            aria-hidden
            className="absolute inset-0 opacity-30"
            style={{
              background:
                'radial-gradient(500px 240px at 50% 0%, rgba(35,166,125,0.4), transparent)',
            }}
          />
          <div className="relative">
            <h2 className="font-display text-2xl font-bold text-white md:text-3xl">
              Ready to explore the platform?
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm text-surface-300 md:text-base">
              Create an account to follow along as new modules go live.
            </p>
            <Link to="/signup" className="mt-7 inline-flex items-center gap-2">
              <Button size="lg">
                Get started
                <ArrowRight className="h-4 w-4" aria-hidden />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* FAQ (§4) — honest answers, no financial claims. */}
      <section className="border-t border-surface-200/70 bg-white">
        <div className="mx-auto w-full max-w-3xl px-4 py-14 md:px-6 md:py-20">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display text-2xl font-bold text-surface-900 md:text-3xl">
              Frequently asked questions
            </h2>
            <p className="mt-3 text-sm text-surface-500 md:text-base">
              Straight answers about what this platform is — and what it is not.
            </p>
          </div>
          <dl className="mt-10 space-y-4">
            {FAQ.map((item) => (
              <div
                key={item.question}
                className="rounded-2xl border border-surface-200 bg-surface-50/60 p-5"
              >
                <dt className="text-sm font-semibold text-surface-900">{item.question}</dt>
                <dd className="mt-2 text-sm leading-relaxed text-surface-600">{item.answer}</dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
    </div>
  );
}
