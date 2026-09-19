"""Withdrawal-aware reconciliation checks (Section 10 §80).

Reports only — never auto-fixes. Extends the Section 5 wallet
reconciliation with withdrawal-specific invariants. All ledger lookups
count only the DEBIT (primary) leg of each operation, because every
wallet-service op writes one row per bucket leg:

    lock      → DEBIT on WITHDRAWABLE  (+ credit on LOCKED)
    release   → DEBIT on LOCKED        (+ credit on WITHDRAWABLE)
    finalize  → DEBIT on LOCKED        (paid out; no offsetting leg)
"""

from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Sum

from apps.accounts.models import User
from apps.wallet.models import WalletTransaction

from .models import Withdrawal

# Ledger conventions written by apps.withdrawals.services.
_REF_TYPE = 'withdrawal'

_ACTIVE_STATUSES = (
    Withdrawal.Status.PENDING,
    Withdrawal.Status.APPROVED,
    Withdrawal.Status.PROCESSING,
)


def _primary_legs(user: User, txn_type: str) -> 'dict[str, dict]':
    """Group the DEBIT legs of a transaction type by reference_id."""
    rows = (
        WalletTransaction.objects.filter(
            user=user,
            transaction_type=txn_type,
            direction=WalletTransaction.Direction.DEBIT,
            reference_type=_REF_TYPE,
        )
        .values('reference_id')
        .annotate(n=Count('id'), total=Sum('amount'))
    )
    return {row['reference_id']: {'count': row['n'], 'total': row['total']} for row in rows}


def reconcile_user_withdrawals(user: User) -> list[str]:
    """Return a list of human-readable issues for one user's withdrawals."""
    issues: list[str] = []
    withdrawals = list(
        Withdrawal.objects.filter(user=user).select_related('network'),
    )
    if not withdrawals:
        # Orphaned lock rows whose withdrawal row is gone entirely.
        locks = _primary_legs(user, WalletTransaction.TransactionType.LOCK)
        orphaned = [ref for ref in locks if ref not in (None, '')]
        # 'pending' placeholders always belong to a withdrawal row; anything
        # else with no matching active status is checked below only when
        # withdrawals exist. With no withdrawals at all, every lock is orphaned.
        if orphaned:
            issues.append(f'{len(orphaned)} lock ledger row(s) without any Withdrawal record')
        return issues

    by_id = {w.withdrawal_id: w for w in withdrawals}
    locks = _primary_legs(user, WalletTransaction.TransactionType.LOCK)
    releases = _primary_legs(user, WalletTransaction.TransactionType.RELEASE)
    finalizes = _primary_legs(user, WalletTransaction.TransactionType.WITHDRAWAL)

    for w in withdrawals:
        wid = w.withdrawal_id
        label = f'{wid}[{w.status}]'
        lock = locks.get(wid)
        release = releases.get(wid)
        finalize = finalizes.get(wid)

        # Fee snapshot sanity (§15–16): net = requested − fee, never negative.
        if w.fee_amount < 0 or w.net_amount < 0:
            issues.append(f'{label}: negative fee/net amount')
        if w.requested_amount - w.fee_amount != w.net_amount:
            issues.append(
                f'{label}: fee mismatch — requested {w.requested_amount} − '
                f'fee {w.fee_amount} ≠ net {w.net_amount}',
            )

        if w.status in _ACTIVE_STATUSES:
            if not lock:
                issues.append(f'{label}: active withdrawal without wallet lock')
            elif lock['total'] != w.requested_amount:
                issues.append(
                    f'{label}: lock total {lock["total"]} ≠ requested {w.requested_amount}',
                )
            if release:
                issues.append(f'{label}: funds released while still {w.status}')
            if finalize:
                issues.append(f'{label}: finalized while still {w.status}')
        elif w.status == Withdrawal.Status.COMPLETED:
            if not finalize:
                issues.append(f'{label}: completed without ledger finalization')
            elif finalize['total'] != w.requested_amount:
                issues.append(
                    f'{label}: finalize total {finalize["total"]} ≠ requested {w.requested_amount}',
                )
            if finalize and finalize['count'] > 1:
                issues.append(f'{label}: {finalize["count"]} duplicate finalization rows')
            if release:
                issues.append(f'{label}: completed but funds were ALSO released')
        elif w.status in (Withdrawal.Status.REJECTED, Withdrawal.Status.FAILED):
            if not release:
                issues.append(f'{label}: {w.status.lower()} without fund release')
            elif release['total'] != w.requested_amount:
                issues.append(
                    f'{label}: release total {release["total"]} ≠ requested {w.requested_amount}',
                )
            if release and release['count'] > 1:
                issues.append(f'{label}: {release["count"]} duplicate release rows')
            if finalize:
                issues.append(f'{label}: {w.status.lower()} but ledger was finalized')

    # Ledger rows pointing at withdrawals that do not exist (invalid reference).
    known = set(by_id) | {'pending'}
    for group_name, group in (('lock', locks), ('release', releases), ('finalize', finalizes)):
        stray = [ref for ref in group if ref not in known]
        for ref in stray:
            issues.append(f'ledger {group_name} row references unknown withdrawal {ref}')

    # Placeholders that were never back-filled: a 'pending' lock whose key
    # never got adopted by a real withdrawal row means the create flow died
    # mid-transaction (should be impossible inside one atomic block).
    stuck = sum(1 for ref in locks if ref == 'pending')
    if stuck:
        issues.append(f'{stuck} un-adjudicated "pending" lock row(s)')

    return issues
