/** Formatting helpers shared across the app. */

const USDT_FORMATTER = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

/** Format a number as a USDT amount, e.g. 1234.5 -> "1,234.50". */
export function formatUsdt(amount: number | string): string {
  const value = typeof amount === 'string' ? Number.parseFloat(amount) : amount;
  if (Number.isNaN(value)) return '0.00';
  return USDT_FORMATTER.format(value);
}

/** Format an ISO date string for display, e.g. "Jan 12, 2026". */
export function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/** Format an ISO date-time string for display, e.g. "Jan 12, 2026, 14:30". */
export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Shorten a crypto address for display, e.g. "TR7NH…9C4f".
 * Used by wallet/deposit sections later.
 */
export function truncateAddress(
  address: string,
  visibleStart = 6,
  visibleEnd = 4,
): string {
  if (!address) return '';
  if (address.length <= visibleStart + visibleEnd) return address;
  return `${address.slice(0, visibleStart)}…${address.slice(-visibleEnd)}`;
}
