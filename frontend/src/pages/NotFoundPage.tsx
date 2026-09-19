import { Link, useLocation } from 'react-router-dom';
import { Compass } from 'lucide-react';
import { Button } from '@/components';
import { Logo } from '@/components/Logo';

/** 404 page for unknown routes. */
export function NotFoundPage() {
  const location = useLocation();

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-surface-50 px-4 text-center">
      <Logo className="h-12 w-12" />
      <p className="mt-6 font-display text-6xl font-extrabold tracking-tight text-surface-900">404</p>
      <h1 className="mt-2 text-lg font-semibold text-surface-900">Page not found</h1>
      <p className="mt-1.5 max-w-sm text-sm text-surface-500">
        Nothing lives at <code className="rounded bg-surface-100 px-1.5 py-0.5 text-xs">{location.pathname}</code>.
        Check the address or head back home.
      </p>
      <Link to="/" className="mt-7">
        <Button leftIcon={<Compass className="h-4 w-4" />}>Back to home</Button>
      </Link>
    </div>
  );
}
