import type { BadgeProps } from '@/components/Badge';

import type { Withdrawal } from '@/types';

/** Withdrawal status → badge tone (mirrors TransactionHistory conventions). */
export function withdrawalStatusTone(status: Withdrawal['status']): BadgeProps['tone'] {
  switch (status) {
    case 'PENDING':
    case 'APPROVED':
    case 'PROCESSING':
      return 'warning';
    case 'COMPLETED':
      return 'success';
    case 'REJECTED':
    case 'FAILED':
      return 'danger';
    default:
      return 'neutral';
  }
}

/**
 * Destination masking helper for UI display. The API list endpoint already
 * returns a masked address; this is a defensive fallback only.
 */
export function maskDestination(address: string): string {
  if (address.length <= 10) return address;
  return `${address.slice(0, 6)}…${address.slice(-4)}`;
}
