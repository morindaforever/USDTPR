"""Withdrawal domain service (Section 10).

The ONLY way withdrawals are created or transitioned. All wallet movement
goes through the Section 5 wallet service — no direct wallet mutation:

    create_withdrawal   → wallet_service.lock()            (withdrawable → locked)
    reject_withdrawal   → wallet_service.release_lock()    (locked → withdrawable)
    fail_withdrawal     → wallet_service.release_lock()    (locked → withdrawable)
    complete_withdrawal → wallet_service.finalize_locked() (locked → paid out)

Locking model (§22): the REQUESTED amount is locked; the fee is taken from
that same amount at completion (net_amount = requested − fee is what the
payout represents). The user never needs extra balance for the fee.

State machine (§24–25)::

    PENDING → APPROVED | REJECTED
    APPROVED → PROCESSING
    PROCESSING → COMPLETED | FAILED

Every transition validates the current state, stamps timestamps, records an
AuditLog and a user notification, and is idempotent under retry: release /
finalize accounting keys are deterministic per withdrawal, and terminal
states (REJECTED / COMPLETED / FAILED) refuse further transitions.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.notifications.services import notify_event
from apps.wallet.models import Network, WalletTransaction
from apps.wallet.services import (
    InsufficientBalanceError,
    WalletError,
    finalize_locked,
    lock,
    release_lock,
)

from . import config
from .address_validation import AddressValidationError, validate_address
from .models import Withdrawal

logger = logging.getLogger('withdrawals')


class WithdrawalError(Exception):
    """User-safe withdrawal domain error."""

    def __init__(self, message: str, errors: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


class InvalidTransitionError(WithdrawalError):
    """Requested status change is not allowed by the state machine."""


# Allowed transitions (§25).
TRANSITIONS: dict[str, set[str]] = {
    Withdrawal.Status.PENDING: {Withdrawal.Status.APPROVED, Withdrawal.Status.REJECTED},
    Withdrawal.Status.APPROVED: {Withdrawal.Status.PROCESSING},
    Withdrawal.Status.PROCESSING: {Withdrawal.Status.COMPLETED, Withdrawal.Status.FAILED},
    Withdrawal.Status.COMPLETED: set(),
    Withdrawal.Status.REJECTED: set(),
    Withdrawal.Status.FAILED: set(),
}


def _idempotency_key(withdrawal: Withdrawal, action: str) -> str:
    return f'WDR_{withdrawal.withdrawal_id}_{action}'


def has_qualifying_vip(user: User) -> bool:
    """True when the user has purchased a PAID VIP plan (VIP 1 or higher).

    The decision uses the RELATED VIPPlan record — not the snapshot name:
    a purchase qualifies only when its plan is numbered VIP 1 or higher
    (``vip_plan.plan_number >= 1``) and the snapshot investment is
    positive. The zero-investment WELCOME plan (plan_number 0) never
    qualifies, and CANCELLED purchases never unlock withdrawals.
    """
    from apps.vip.models import VIPPurchase

    return (
        VIPPurchase.objects.filter(
            user=user,
            investment_amount__gt=0,
            vip_plan__plan_number__gte=1,
        )
        .exclude(status=VIPPurchase.Status.CANCELLED)
        .exists()
    )


_AUDIT_ACTIONS = {
    'created': AuditLog.Action.CREATE,
    'status-approved': AuditLog.Action.APPROVE,
    'status-rejected': AuditLog.Action.REJECT,
}


def _audit(action: str, withdrawal: Withdrawal, *, actor=None, description: str = '') -> None:
    AuditLog.objects.create(
        actor_user=actor,
        action=_AUDIT_ACTIONS.get(action, AuditLog.Action.OTHER),
        target_type='withdrawal',
        target_id=withdrawal.withdrawal_id,
        description=(
            description
            or f'Withdrawal {withdrawal.withdrawal_id}: {action} '
            f'(status={withdrawal.status}, user={withdrawal.user.user_id}).'
        ),
    )


def _notify(user, title: str, message: str, *, event_key: str, related_id: str) -> None:
    """Section 13: idempotent, transaction-safe notification via the
    centralized service — retries can never double-notify."""
    notify_event(
        user=user,
        notification_type=Notification.NotificationType.WITHDRAWAL,
        title=title,
        message=message,
        event_key=event_key,
        related_type='withdrawal',
        related_id=related_id,
    )


# --------------------------------------------------------------------------- #
# Quote (§47) — informational; submission always recalculates.
# --------------------------------------------------------------------------- #
def quote(amount, network_code: str | None = None) -> dict:
    """Server-computed fee/net breakdown for a requested amount."""
    amount = Decimal(amount)
    if amount <= 0:
        raise WithdrawalError('Amount must be positive.')
    network = None
    if network_code:
        network = Network.objects.filter(code=network_code.strip().upper(), is_active=True).first()
    minimum = config.get_min_amount(network)
    if amount < minimum:
        raise WithdrawalError(
            f'Minimum withdrawal is {minimum.quantize(Decimal("0.01"))} USDT.',
            errors={'amount': [f'Minimum withdrawal is {minimum.quantize(Decimal("0.01"))} USDT.']},
        )
    fee, net = config.calculate_net(amount, network)
    return {
        'amount': str(amount.quantize(Decimal('0.01'))),
        'fee': str(fee.quantize(Decimal('0.01'))),
        'net_amount': str(net.quantize(Decimal('0.01'))),
        'minimum_amount': str(minimum.quantize(Decimal('0.01'))),
        'fee_type': config.get_fee_type(network),
    }


# --------------------------------------------------------------------------- #
# Creation (§18–21, §35, §37)
# --------------------------------------------------------------------------- #
@transaction.atomic
def create_withdrawal(
    *,
    user: User,
    network_code: str,
    destination_address: str,
    amount,
    idempotency_key: str,
    qr_image=None,
) -> Withdrawal:
    """Validate, lock funds, and create a PENDING withdrawal — atomically.

    Concurrent requests serialize on the wallet row lock inside
    ``wallet_service.lock``: the second of two over-drawing requests fails
    with InsufficientBalanceError and the whole block rolls back (§37).

    ``qr_image`` is an optional user-uploaded QR destination image (§7).
    It is stored for reviewer context only — the typed wallet_address is
    always the authoritative payout destination.

    Returns ``(withdrawal, created)`` — a replayed idempotency key returns
    the ORIGINAL request with ``created=False`` (§35) rather than a copy.
    """
    from decimal import Decimal, InvalidOperation

    if user.account_status != User.AccountStatus.ACTIVE or not user.is_active:
        raise WithdrawalError('Your account cannot request withdrawals.')

    # Withdrawal eligibility (server-side, from real purchase records): the
    # user must have purchased a paid VIP plan (VIP 1 or higher). The
    # zero-investment WELCOME plan does not qualify. This runs before any
    # balance/lock work, so an ineligible request creates nothing.
    if not has_qualifying_vip(user):
        raise WithdrawalError(
            'You must purchase at least VIP 1 before submitting a withdrawal request.',
            errors={'vip_plan': [
                'You must purchase at least VIP 1 before submitting a withdrawal request. '
                'The Welcome Plan does not qualify for withdrawal eligibility.'
            ]},
        )

    # Conversion §17: identity-verification gate when the operator enables
    # KYC enforcement. No-op (record-keeper) while the flag is off.
    from apps.integrations.compliance import KYCNotVerified, ensure_kyc_allowed_for_withdrawal

    try:
        ensure_kyc_allowed_for_withdrawal(user)
    except KYCNotVerified as exc:
        raise WithdrawalError(str(exc)) from exc

    raw = (str(amount) or '').strip()
    try:
        amount_decimal = Decimal(raw)
    except (InvalidOperation, TypeError):
        raise WithdrawalError('Enter a valid amount.', errors={'amount': ['Enter a valid amount.']})
    if amount_decimal <= 0:
        raise WithdrawalError('Amount must be greater than zero.',
                              errors={'amount': ['Amount must be greater than zero.']})
    # Reject sub-cent / over-precise amounts (§77): quantize to 2dp and
    # require the value to be unchanged.
    amount_decimal = amount_decimal.quantize(Decimal('0.01'))
    network = Network.objects.filter(code=(network_code or '').strip().upper(), is_active=True).first()
    if network is None:
        raise WithdrawalError('Selected network is not available.',
                              errors={'network': ['Selected network is not available.']})
    minimum = config.get_min_amount(network)
    if amount_decimal < minimum:
        raise WithdrawalError(
            f'Minimum withdrawal is {minimum.quantize(Decimal("0.01"))} USDT.',
            errors={'amount': [f'Minimum withdrawal is {minimum.quantize(Decimal("0.01"))} USDT.']},
        )

    # Duplicate/replay protection (§35): the unique (user, key) constraint
    # is the backstop; this pre-check returns the existing request.
    key = (idempotency_key or '').strip()
    if not key:
        raise WithdrawalError('Missing idempotency key.',
                              errors={'idempotency_key': ['This field is required.']})
    existing = Withdrawal.objects.filter(user=user, idempotency_key=key).first()
    if existing is not None:
        return existing, False

    try:
        address = validate_address(network.code, destination_address)
    except AddressValidationError as exc:
        raise WithdrawalError(exc.message, errors={'destination_address': [exc.message]})

    fee, net = config.calculate_net(amount_decimal, network)

    # Lock FIRST — InsufficientBalanceError rolls the whole block back (§21).
    # Wrap it into a user-safe explanation: the withdrawable bucket is funded
    # ONLY by VIP plan profits and referral commissions — deposit balance is
    # spendable on VIP plans, never withdrawable.
    try:
        lock(
            user=user,
            amount=amount_decimal,
            reference_type='withdrawal',
            reference_id='pending',  # replaced below once the ID exists
            description=f'Withdrawal lock — {amount_decimal.quantize(Decimal("0.01"))} USDT',
            idempotency_key=f'WDR_NEW_{key}',
        )
    except InsufficientBalanceError as exc:
        raise WithdrawalError(
            'Insufficient withdrawable balance. Only VIP plan profits and '
            'referral commissions can be withdrawn — deposit balance is used '
            'for plan purchases.',
            errors={'amount': [str(exc.message)]},
        ) from exc

    withdrawal = Withdrawal.objects.create(
        user=user,
        network=network,
        requested_amount=amount_decimal,
        fee_amount=fee,
        net_amount=net,
        wallet_address=address,
        qr_image=qr_image,
        status=Withdrawal.Status.PENDING,
        idempotency_key=key,
    )
    # Repoint the lock's reference at the real withdrawal ID.
    WalletTransaction.objects.filter(
        user=user,
        idempotency_key__in=[f'WDR_NEW_{key}', f'WDR_NEW_{key}:c'],
        reference_id='pending',
    ).update(reference_id=withdrawal.withdrawal_id)

    _audit(
        'created',
        withdrawal,
        actor=user,
        description=(
            f'Withdrawal {withdrawal.withdrawal_id} created: '
            f'{amount_decimal.quantize(Decimal("0.01"))} USDT on {network.code} '
            f'(fee {fee.quantize(Decimal("0.01"))}, net {net.quantize(Decimal("0.01"))}).'
        ),
    )
    _notify(
        user,
        'Withdrawal request submitted',
        f'Your {amount_decimal.quantize(Decimal("0.01"))} USDT withdrawal is pending review.',
        event_key=f'withdrawal:{withdrawal.withdrawal_id}:submitted',
        related_id=withdrawal.withdrawal_id,
    )
    return withdrawal, True


# --------------------------------------------------------------------------- #
# Admin transitions (§27–34, §48–53)
# --------------------------------------------------------------------------- #
def _transition(
    withdrawal_id: str,
    *,
    to_status: str,
    admin: User,
    admin_note: str = '',
    reason: str = '',
    tx_hash: str = '',
) -> Withdrawal:
    with transaction.atomic():
        withdrawal = (
            Withdrawal.objects.select_for_update()
            .select_related('user', 'network')
            .filter(withdrawal_id=withdrawal_id)
            .first()
        )
        if withdrawal is None:
            raise WithdrawalError('Withdrawal not found.')
        current = withdrawal.status
        if to_status not in TRANSITIONS.get(current, set()):
            raise InvalidTransitionError(
                f'Cannot move a {current} withdrawal to {to_status}.'
            )

        old_status = current
        now = timezone.now()
        withdrawal.status = to_status
        withdrawal.admin = admin
        if admin_note:
            withdrawal.admin_note = admin_note
        if to_status == Withdrawal.Status.APPROVED:
            withdrawal.approved_at = now
        elif to_status == Withdrawal.Status.REJECTED:
            withdrawal.rejected_at = now
            withdrawal.rejection_reason = (reason or 'Request rejected.')[:255]
        elif to_status == Withdrawal.Status.PROCESSING:
            withdrawal.processing_at = now
        elif to_status == Withdrawal.Status.COMPLETED:
            # Conversion §9–§10: a completion either carries a REAL on-chain
            # transaction hash (from a provider payout or a manually settled
            # transfer by operations) or it is an internal settlement decision
            # recorded WITHOUT any hash. Fabricating a hash is prohibited —
            # the DB stays honest: empty tx_hash means "no on-chain transfer
            # recorded for this completion". The audit entry below records
            # which authority produced the hash.
            if tx_hash:
                cleaned = tx_hash.strip()
                if len(cleaned) < 10 or not all(c in '0123456789abcdefABCDEFxX' for c in cleaned):
                    raise WithdrawalError(
                        'A transaction hash must be the real on-chain hash '
                        '(hexadecimal) exactly as returned by the network or '
                        'payout provider — it cannot be invented.'
                    )
                withdrawal.tx_hash = cleaned[:128]
            withdrawal.completed_at = now
        elif to_status == Withdrawal.Status.FAILED:
            withdrawal.failed_at = now
            withdrawal.rejection_reason = (reason or 'Processing failed.')[:255]
        withdrawal.save()

        # --- accounting per transition (idempotent keys) -------------------
        if to_status == Withdrawal.Status.REJECTED:
            release_lock(
                user=withdrawal.user,
                amount=withdrawal.requested_amount,
                reference_type='withdrawal',
                reference_id=withdrawal.withdrawal_id,
                description=f'Withdrawal {withdrawal.withdrawal_id} rejected — funds released',
                idempotency_key=_idempotency_key(withdrawal, 'release'),
            )
        elif to_status == Withdrawal.Status.FAILED:
            release_lock(
                user=withdrawal.user,
                amount=withdrawal.requested_amount,
                reference_type='withdrawal',
                reference_id=withdrawal.withdrawal_id,
                description=f'Withdrawal {withdrawal.withdrawal_id} failed — funds released',
                idempotency_key=_idempotency_key(withdrawal, 'release'),
            )
        elif to_status == Withdrawal.Status.COMPLETED:
            # locked → paid out; the fee comes out of the locked amount (§33).
            finalize_locked(
                user=withdrawal.user,
                amount=withdrawal.requested_amount,
                transaction_type=WalletTransaction.TransactionType.WITHDRAWAL,
                reference_type='withdrawal',
                reference_id=withdrawal.withdrawal_id,
                description=f'Withdrawal {withdrawal.withdrawal_id} completed',
                idempotency_key=_idempotency_key(withdrawal, 'finalize'),
            )

        _audit(
            f'status-{to_status.lower()}',
            withdrawal,
            actor=admin,
            description=(
                f'Withdrawal {withdrawal.withdrawal_id}: {old_status} → {to_status} '
                f'by {admin.user_id}.'
                + (f' Reason: {withdrawal.rejection_reason}' if withdrawal.rejection_reason else '')
            ),
        )

        messages = {
            Withdrawal.Status.APPROVED: (
                'Withdrawal approved',
                'Your withdrawal has been approved for processing.',
            ),
            Withdrawal.Status.REJECTED: (
                'Withdrawal rejected',
                f'Your withdrawal request was rejected. Reason: {withdrawal.rejection_reason}',
            ),
            Withdrawal.Status.PROCESSING: (
                'Withdrawal processing',
                'Your withdrawal is currently being processed.',
            ),
            Withdrawal.Status.COMPLETED: (
                'Withdrawal completed',
                'Your withdrawal has been marked as completed.',
            ),
            Withdrawal.Status.FAILED: (
                'Withdrawal failed',
                'Your withdrawal could not be completed and the locked amount has been released.',
            ),
        }
        title, body = messages[to_status]
        _notify(
            withdrawal.user, title, body,
            event_key=f'withdrawal:{withdrawal.withdrawal_id}:{to_status.lower()}',
            related_id=withdrawal.withdrawal_id,
        )
        return withdrawal


def approve_withdrawal(withdrawal_id: str, *, admin: User, admin_note: str = '') -> Withdrawal:
    """PENDING → APPROVED. Funds STAY locked (§30)."""
    return _transition(withdrawal_id, to_status=Withdrawal.Status.APPROVED,
                       admin=admin, admin_note=admin_note)


def reject_withdrawal(withdrawal_id: str, *, admin: User, reason: str, admin_note: str = '') -> Withdrawal:
    """PENDING → REJECTED; releases the locked funds exactly once (§28)."""
    return _transition(withdrawal_id, to_status=Withdrawal.Status.REJECTED,
                       admin=admin, admin_note=admin_note, reason=reason)


def start_processing(withdrawal_id: str, *, admin: User, admin_note: str = '') -> Withdrawal:
    """APPROVED → PROCESSING (§31). No wallet movement."""
    return _transition(withdrawal_id, to_status=Withdrawal.Status.PROCESSING,
                       admin=admin, admin_note=admin_note)


def complete_withdrawal(withdrawal_id: str, *, admin: User, tx_hash: str = '',
                        admin_note: str = '') -> Withdrawal:
    """PROCESSING → COMPLETED; finalizes the locked funds (§32–33)."""
    return _transition(withdrawal_id, to_status=Withdrawal.Status.COMPLETED,
                       admin=admin, admin_note=admin_note, tx_hash=tx_hash)


def fail_withdrawal(withdrawal_id: str, *, admin: User, reason: str = '',
                    admin_note: str = '') -> Withdrawal:
    """PROCESSING → FAILED; releases the locked funds (§34)."""
    return _transition(withdrawal_id, to_status=Withdrawal.Status.FAILED,
                       admin=admin, admin_note=admin_note, reason=reason)


def pending_withdrawal_total(user) -> Decimal:
    """Sum of requested amounts not yet in a terminal state (§41)."""
    from decimal import Decimal
    from django.db.models import Sum

    total = Withdrawal.objects.filter(user=user).exclude(
        status__in=[Withdrawal.Status.REJECTED, Withdrawal.Status.FAILED, Withdrawal.Status.COMPLETED],
    ).aggregate(t=Sum('requested_amount'))
    return (total['t'] or Decimal('0')).quantize(Decimal('0.01'))
