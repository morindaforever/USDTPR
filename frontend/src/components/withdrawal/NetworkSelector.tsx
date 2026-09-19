import { useState } from 'react';
import { Check, Copy, ShieldAlert } from 'lucide-react';
import { cn } from '@/utils/cn';

import type { WithdrawalNetwork } from '@/types';

interface NetworkSelectorProps {
  networks: WithdrawalNetwork[];
  value: string | null;
  disabled?: boolean;
  onChange: (code: string) => void;
}

/**
 * Network picker (§8). Selection gates address/amount entry; the backend
 * re-validates that the chosen network is active and withdrawal-capable.
 */
export function NetworkSelector({ networks, value, disabled = false, onChange }: NetworkSelectorProps) {
  const [copied, setCopied] = useState<string | null>(null);

  const copyAddress = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(code);
      window.setTimeout(() => setCopied(null), 1500);
    } catch {
      // Clipboard unavailable — selection still works.
    }
  };

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
      {networks.map((network) => {
        const selected = network.code === value;
        return (
          <button
            key={network.code}
            type="button"
            disabled={disabled}
            onClick={() => onChange(network.code)}
            className={cn(
              'group relative rounded-xl border p-3 text-left transition-all',
              'disabled:pointer-events-none disabled:opacity-60',
              selected
                ? 'border-brand-500 bg-brand-50 ring-1 ring-brand-500'
                : 'border-surface-200 bg-white hover:border-brand-300 hover:bg-brand-50/40',
            )}
          >
            <span className="flex items-center justify-between">
              <span className="text-sm font-semibold text-surface-900">{network.code}</span>
              {selected && (
                <Check className="h-4 w-4 text-brand-600" aria-hidden />
              )}
            </span>
            <span className="mt-0.5 block text-xs text-surface-500">{network.name}</span>
            <span
              role="button"
              tabIndex={0}
              aria-label={`Copy ${network.code} network code`}
              onClick={(event) => {
                event.stopPropagation();
                void copyAddress(network.code);
              }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.stopPropagation();
                  void copyAddress(network.code);
                }
              }}
              className="mt-2 inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-surface-400 hover:text-brand-600"
            >
              {copied === network.code ? (
                <>
                  <Check className="h-3 w-3" aria-hidden /> copied
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" aria-hidden /> {network.asset}
                </>
              )}
            </span>
            {selected && network.address_hint ? (
              <span className="mt-1.5 flex items-start gap-1 text-[10px] leading-tight text-surface-500">
                <ShieldAlert className="h-3 w-3 shrink-0 text-amber-500" aria-hidden />
                {network.address_hint}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
