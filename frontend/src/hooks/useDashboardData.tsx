import { useCallback, useEffect, useRef, useState } from 'react';

interface State<T> {
  data: T | null;
  isLoading: boolean;
  error: string | null;
}

/**
 * Minimal fetch wrapper giving every dashboard card a consistent
 * loading / error / retry contract. `pollMs` optionally re-fetches on an
 * interval. `deps` re-fetches when the given reactive inputs change (server-driven search/filters/pagination —
 * used by the admin tables).
 */
export function useDashboardData<T>(
  fetcher: () => Promise<T>,
  options: { pollMs?: number; enabled?: boolean; deps?: readonly unknown[] } = {},
): State<T> & { retry: () => void } {
  const { pollMs, enabled = true, deps } = options;
  const [state, setState] = useState<State<T>>({ data: null, isLoading: true, error: null });
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const [tick, setTick] = useState(0);
  const depsKey = deps ? JSON.stringify(deps) : null;

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    fetcherRef
      .current()
      .then((data) => {
        if (!cancelled) setState({ data, isLoading: false, error: null });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : 'Something went wrong.';
        setState({ data: null, isLoading: false, error: message });
      });
    return () => {
      cancelled = true;
    };
  }, [tick, enabled, depsKey]);

  useEffect(() => {
    if (!pollMs || !enabled) return;
    const id = window.setInterval(() => setTick((t) => t + 1), pollMs);
    return () => window.clearInterval(id);
  }, [pollMs, enabled]);

  const retry = useCallback(() => setTick((t) => t + 1), []);

  return { ...state, retry };
}

/** Shared skeleton bar used by dashboard loading states. */
export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-lg bg-surface-200/70 ${className}`} />;
}
