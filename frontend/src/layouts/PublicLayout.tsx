import { Link, Outlet } from 'react-router-dom';
import { Logo } from '@/components/Logo';

/**
 * Shell for public pages (landing, auth, about, help). Marketing header
 * with login/signup actions and a global footer.
 */
export function PublicLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-surface-50">
      <header className="sticky top-0 z-40 border-b border-surface-200/70 bg-white/85 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-5xl items-center justify-between px-4 md:px-6">
          <Link to="/" className="flex items-center gap-2" aria-label="NexusUSDT home">
            <Logo className="h-8 w-8" />
            <span className="font-display text-lg font-bold tracking-tight text-surface-900">
              Nexus<span className="text-brand-600">USDT</span>
            </span>
          </Link>
          <div className="flex items-center gap-2">
            <Link
              to="/login"
              className="rounded-xl px-3.5 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-100"
            >
              Log in
            </Link>
            <Link
              to="/signup"
              className="rounded-xl bg-brand-600 px-3.5 py-2 text-sm font-semibold text-white shadow-sm transition-colors hover:bg-brand-700"
            >
              Sign up
            </Link>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-surface-200/70 bg-white">
        <div className="mx-auto w-full max-w-5xl px-4 py-8 md:px-6">
          <div className="flex flex-col gap-6 md:flex-row md:items-start md:justify-between">
            <div className="max-w-sm">
              <div className="flex items-center gap-2">
                <Logo className="h-6 w-6" />
                <span className="font-display text-sm font-bold text-surface-900">
                  Nexus<span className="text-brand-600">USDT</span>
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-surface-500">
                A platform for USDT deposits, VIP tiers, and team rewards.
                This project is under development — features ship section by section.
              </p>
            </div>
            <nav aria-label="Footer" className="flex gap-10">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-surface-400">Product</p>
                <ul className="mt-2 space-y-1.5 text-sm">
                  <li><Link className="text-surface-600 hover:text-brand-700" to="/">Home</Link></li>
                  <li><Link className="text-surface-600 hover:text-brand-700" to="/about">About</Link></li>
                </ul>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-surface-400">Support</p>
                <ul className="mt-2 space-y-1.5 text-sm">
                  <li><Link className="text-surface-600 hover:text-brand-700" to="/help">Help center</Link></li>
                  <li><Link className="text-surface-600 hover:text-brand-700" to="/signup">Create account</Link></li>
                </ul>
              </div>
            </nav>
          </div>
          <div className="mt-8 border-t border-surface-100 pt-4">
            <p className="text-[11px] leading-relaxed text-surface-400">
              © {new Date().getFullYear()} NexusUSDT. Not financial advice. No statement on this
              site is a promise of returns. Cryptocurrency involves risk.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
