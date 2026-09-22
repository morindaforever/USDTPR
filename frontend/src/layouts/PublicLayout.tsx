import { Link, Outlet } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { TelegramIcon } from '@/components/TelegramIcon';
import { TELEGRAM_CHANNEL_URL } from '@/constants';

/**
 * Shell for public pages (landing, auth, about, help). Marketing header
 * with login/signup actions and a global footer.
 */
export function PublicLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-surface-950">
      <header className="sticky top-0 z-40 border-b border-surface-200/80 bg-surface-950/80 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-4 md:px-6">
          <Link to="/" className="flex items-center gap-2" aria-label="NexusUSDT home">
            <Logo className="h-8 w-8" />
            <span className="font-display text-lg font-bold tracking-tight text-surface-800">
              Nexus<span className="text-brand-400">USDT</span>
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="rounded-xl px-3.5 py-2 text-sm font-semibold text-surface-600 transition-colors hover:bg-surface-100 hover:text-surface-800"
            >
              Log in
            </Link>
            <Link
              to="/signup"
              className="rounded-xl bg-brand-500 px-3.5 py-2 text-sm font-semibold text-white shadow-glow transition-colors hover:bg-brand-400"
            >
              Sign up
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-surface-200 bg-surface-900/40">
        <div className="mx-auto w-full max-w-6xl px-4 py-10 md:px-6">
          <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
            <div className="max-w-sm">
              <div className="flex items-center gap-2">
                <Logo className="h-6 w-6" />
                <span className="font-display text-sm font-bold text-surface-800">
                  Nexus<span className="text-brand-400">USDT</span>
                </span>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-surface-500">
                A USDT-based digital investment platform with tiered plans, daily reward
                cycles, and a referral team program. Cryptocurrency involves risk.
              </p>
            </div>
            <nav aria-label="Footer" className="flex gap-12">
              <div>
                <p className="eyebrow">Platform</p>
                <ul className="mt-3 space-y-2 text-sm">
                  <li><Link className="text-surface-600 transition-colors hover:text-brand-400" to="/">Home</Link></li>
                  <li><Link className="text-surface-600 transition-colors hover:text-brand-400" to="/about">About</Link></li>
                  <li><Link className="text-surface-600 transition-colors hover:text-brand-400" to="/signup">Create account</Link></li>
                </ul>
              </div>
              <div>
                <p className="eyebrow">Support</p>
                <ul className="mt-3 space-y-2 text-sm">
                  <li><Link className="text-surface-600 transition-colors hover:text-brand-400" to="/help">Help center</Link></li>
                  <li><Link className="text-surface-600 transition-colors hover:text-brand-400" to="/login">Log in</Link></li>
                </ul>
              </div>
              <div>
                <p className="eyebrow">Community</p>
                <ul className="mt-3 space-y-2 text-sm">
                  <li>
                    <a
                      className="inline-flex items-center gap-1.5 text-surface-600 transition-colors hover:text-brand-400"
                      href={TELEGRAM_CHANNEL_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <TelegramIcon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                      Telegram
                    </a>
                  </li>
                </ul>
              </div>
            </nav>
          </div>
          <div className="mt-10 border-t border-surface-200 pt-5">
            <p className="text-[11px] leading-relaxed text-surface-500">
              © {new Date().getFullYear()} NexusUSDT. Not financial advice. No statement on this
              site is a promise of returns. Digital assets and investment activities involve
              risk; returns are not guaranteed.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
