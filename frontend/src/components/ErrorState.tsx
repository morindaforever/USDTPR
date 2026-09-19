import { AlertTriangle, RefreshCw } from 'lucide-react';
import { Button } from './Button';

export interface ErrorStateProps {
  title?: string;
  message?: string;
  /** When provided, renders a retry button calling this handler. */
  onRetry?: () => void;
}

/** Shown when a data fetch fails; keeps the user oriented with a retry path. */
export function ErrorState({
  title = 'Something went wrong',
  message = 'An unexpected error occurred while loading this content. Please try again.',
  onRetry,
}: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-red-100 bg-red-50/60 px-6 py-10 text-center"
    >
      <div className="flex h-11 w-11 items-center justify-center rounded-full bg-red-100 text-red-500">
        <AlertTriangle className="h-5 w-5" aria-hidden />
      </div>
      <p className="text-sm font-semibold text-red-900">{title}</p>
      <p className="max-w-xs text-xs text-red-700/80">{message}</p>
      {onRetry && (
        <Button variant="outline" size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
