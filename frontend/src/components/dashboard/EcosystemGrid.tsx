import { Badge } from '@/components';

/**
 * Compatible ecosystem names rendered as neutral text tiles. Deliberately
 * labeled "Supported Ecosystem" — these are NOT partners, sponsors, or
 * investors, and no endorsement is implied. Text marks are used instead of
 * brand logos since their use isn't licensed here.
 */
const ECOSYSTEM = [
  'Binance',
  'Coinbase',
  'CoinDCX',
  'CoinSwitch',
  'Bitmain',
  'Huobi',
  'Bitget Wallet',
  'Trust Wallet',
] as const;

export function EcosystemGrid() {
  return (
    <section aria-labelledby="ecosystem-heading">
      <div className="mb-3 flex items-center justify-between">
        <h2 id="ecosystem-heading" className="text-sm font-semibold text-surface-800">
          Supported ecosystem
        </h2>
        <Badge tone="neutral">Compatible platforms</Badge>
      </div>
      <ul className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {ECOSYSTEM.map((name) => (
          <li
            key={name}
            className="flex items-center justify-center rounded-2xl border border-surface-200 bg-surface-50 px-3 py-4"
          >
            <span
              aria-hidden
              className="mr-2 inline-flex h-6 w-6 items-center justify-center rounded-full bg-surface-900 text-[10px] font-bold text-surface-800"
            >
              {name.charAt(0)}
            </span>
            <span className="text-sm font-semibold text-surface-800">{name}</span>
          </li>
        ))}
      </ul>
      <p className="mt-2 text-center text-[11px] text-surface-500">
        Independent platforms in the broader crypto ecosystem. No partnership or endorsement implied.
      </p>
    </section>
  );
}
