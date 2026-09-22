import { useEffect, useMemo, useState } from 'react';
import { Timer } from 'lucide-react';

interface RewardCountdownProps {
  /** ISO timestamp of the next scheduled reward. */
  nextRewardAt: string;
}

function parts(msRemaining: number): { h: string; m: string; s: string } {
  const clamped = Math.max(0, msRemaining);
  const totalSeconds = Math.floor(clamped / 1000);
  return {
    h: String(Math.floor(totalSeconds / 3600)).padStart(2, '0'),
    m: String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0'),
    s: String(totalSeconds % 60).padStart(2, '0'),
  };
}

/**
 * Purely visual countdown to the next reward. When it reaches zero it shows
 * "Reward processing…" and stops — crediting rewards is the backend/Celery
 * reward engine's job (Section 8), never this component's.
 */
export function RewardCountdown({ nextRewardAt }: RewardCountdownProps) {
  const target = useMemo(() => new Date(nextRewardAt).getTime(), [nextRewardAt]);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const remaining = target - now;
  const { h, m, s } = parts(remaining);

  return (
    <div className="mt-3 flex items-center justify-between rounded-xl bg-surface-100 px-3 py-2.5">
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-surface-600">
        <Timer className="h-4 w-4 text-brand-400" aria-hidden />
        Next reward
      </span>
      {remaining <= 0 ? (
        <span className="text-sm font-semibold text-brand-400">Reward processing…</span>
      ) : (
        <span className="font-mono text-sm font-semibold tabular-nums text-surface-800" aria-live="off">
          {h}h {m}m {s}s
        </span>
      )}
    </div>
  );
}
