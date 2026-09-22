import { useState } from 'react';
import { Check, Copy, Share2 } from 'lucide-react';

interface ReferralLinkCardProps {
  link: string;
  code: string;
}

/**
 * Shareable referral link (§25–26): Clipboard API copy with a transient
 * "copied" confirmation, and Web Share when supported (copy fallback).
 * The link itself comes from the backend (env-configured base URL).
 */
export function ReferralLinkCard({ link, code }: ReferralLinkCardProps) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard unavailable (permissions/insecure context) — select fallback.
      // The link is visible in the readonly input so users can copy manually.
    }
  };

  const share = async () => {
    if (typeof navigator.share === 'function') {
      try {
        await navigator.share({ title: 'Join me on NexusUSDT', url: link });
        return;
      } catch {
        /* user dismissed the share sheet — fall through to copy */
      }
    }
    await copy();
  };

  return (
    <div className="relative overflow-hidden rounded-2xl border border-brand-500/25 bg-brand-950/20 p-5">
      <p className="text-sm font-semibold text-surface-800">Your Referral Link</p>
      <div className="mt-3 flex items-center gap-2">
        <div className="flex h-11 min-w-0 flex-1 items-center truncate rounded-xl border border-surface-300 bg-surface-900/70 px-3.5 text-sm text-surface-700">
          <span className="truncate font-mono text-xs">{link}</span>
        </div>
        <button
          type="button"
          onClick={copy}
          aria-label="Copy referral link"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-surface-300 bg-surface-100 text-surface-600 transition-colors hover:bg-surface-200"
        >
          {copied ? (
            <Check className="h-4 w-4 text-brand-400" aria-hidden />
          ) : (
            <Copy className="h-4 w-4" aria-hidden />
          )}
        </button>
        <button
          type="button"
          onClick={share}
          aria-label="Share referral link"
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-500 text-white shadow-glow transition-colors hover:bg-brand-400"
        >
          <Share2 className="h-4 w-4" aria-hidden />
        </button>
      </div>
      {copied && (
        <p className="mt-2 text-xs font-medium text-brand-400" role="status">
          Referral link copied
        </p>
      )}
      <div className="mt-3 flex items-center justify-between rounded-xl border border-surface-200 bg-surface-900/50 px-3.5 py-2.5">
        <span className="text-xs text-surface-500">Referral Code</span>
        <span className="font-mono text-sm font-semibold tracking-wider text-surface-800">
          {code}
        </span>
      </div>
    </div>
  );
}
