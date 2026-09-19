import { formatDate, formatUsdt } from '@/utils/format';
import type { VipPurchase } from '@/types';

const STATUS_TONES: Record<VipPurchase['status'], string> = {
  ACTIVE: 'bg-brand-50 text-brand-700 ring-brand-200',
  PENDING: 'bg-amber-50 text-amber-700 ring-amber-200',
  COMPLETED: 'bg-sky-50 text-sky-700 ring-sky-200',
  CANCELLED: 'bg-surface-100 text-surface-500 ring-surface-200',
};

/** Simple purchase history list (newest first from the API). */
export function VipPurchaseHistory({ purchases }: { purchases: VipPurchase[] }) {
  if (purchases.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-surface-200 p-5 text-center text-sm text-surface-500">
        No purchases yet.
      </p>
    );
  }
  return (
    <ul className="space-y-2.5">
      {purchases.map((purchase) => (
        <li
          key={purchase.purchase_id}
          className="flex items-center justify-between gap-3 rounded-2xl border border-surface-200 bg-white p-4"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-surface-900">
              {purchase.plan_name}
              <span className="ml-2 text-[11px] font-normal text-surface-400">
                {purchase.purchase_id}
              </span>
            </p>
            <p className="mt-0.5 text-xs text-surface-500">
              {purchase.investment_amount === '0.00000000'
                ? 'Free'
                : `${formatUsdt(purchase.investment_amount)} USDT`}{' '}
              · {formatDate(purchase.created_at)}
            </p>
          </div>
          <span
            className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${STATUS_TONES[purchase.status] ?? STATUS_TONES.PENDING}`}
          >
            {purchase.status}
          </span>
        </li>
      ))}
    </ul>
  );
}
