import { RefreshCw, WifiOff } from 'lucide-react';
import { Button } from '@/components';
import { Logo } from '@/components/Logo';

/**
 * Top-level error boundary fallback for unexpected render errors.
 * Route-level loading is handled by Suspense; API failures use ErrorState.
 */
export function ErrorPage({ onReset }: { onReset?: () => void }) {
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-surface-50 px-4 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-danger-50 text-danger-500">
        <WifiOff className="h-6 w-6" aria-hidden />
      </div>
      <h1 className="mt-6 font-display text-xl font-bold text-surface-800">
        Something went wrong
      </h1>
      <p className="mt-1.5 max-w-sm text-sm text-surface-500">
        An unexpected error occurred. Your data is safe — try reloading the page.
      </p>
      <div className="mt-7 flex gap-2">
        <Button
          variant="outline"
          onClick={() => window.location.reload()}
          leftIcon={<RefreshCw className="h-4 w-4" />}
        >
          Reload
        </Button>
        {onReset && <Button onClick={onReset}>Try again</Button>}
      </div>
      <p className="mt-10 flex items-center gap-1.5 text-xs text-surface-500">
        <Logo className="h-4 w-4" /> NexusUSDT
      </p>
    </div>
  );
}
