"""Deposit domain services.

All business rules for deposits live here — views only translate HTTP.

Invariants enforced:
- Submission NEVER touches the wallet; only admin approval credits.
- Approval is atomic: deposit state + wallet credit + audit + notification
  commit together, using the Section 5 wallet service (never direct writes).
- Approval is idempotent: the wallet-service idempotency key is derived from
  the deposit's primary key, so double approval cannot double credit.
- The deposit stores the address shown to the user at submission time;
  later address changes never rewrite history.
- Duplicate protection: the same (tx_hash, network, user) cannot be
  submitted twice while a previous submission is PENDING/APPROVED.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditLog
from apps.accounts.services import AuthError, ensure_active
from apps.notifications.models import Notification
from apps.notifications.services import notify_event
from apps.wallet.models import DepositAddress, Network
from apps.wallet.services import (
    WalletError,
    credit,
    normalize_amount,
)

from .models import Deposit

# Development default; overridable via the SiteSetting key 'deposit.min_amount'
# (the key surfaced in the admin settings UI — Section 15 consistency fix).
DEFAULT_MIN_DEPOSIT = Decimal('1.00000000')
MIN_DEPOSIT_SETTING_KEY = 'deposit.min_amount'


class DepositError(Exception):
    """Domain error with a user-safe message."""

    def __init__(self, message: str, errors: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


def get_minimum_deposit() -> Decimal:
    """Configurable minimum deposit (SiteSetting), falling back to default."""
    from apps.core.models import SiteSetting

    row = SiteSetting.objects.filter(key=MIN_DEPOSIT_SETTING_KEY).first()
    if row is None:
        return DEFAULT_MIN_DEPOSIT
    try:
        return normalize_amount(row.value)
    except WalletError:
        return DEFAULT_MIN_DEPOSIT


def list_active_networks() -> list[Network]:
    return list(Network.objects.filter(is_active=True).order_by('sort_order', 'code'))


def get_active_address(network: Network) -> DepositAddress | None:
    return (
        DepositAddress.objects.filter(network=network, asset=network.asset, is_active=True)
        .order_by('-created_at')
        .first()
    )


def qr_code_data_uri(address: DepositAddress) -> str | None:
    """Render the deposit address as a QR PNG data URI (backend-authoritative).

    QR is generated on demand from the exact address being displayed, so it
    can never encode a different address than the one shown. The model's
    ``qr_code`` path is used only as a fallback reference in the future.
    """
    import base64
    import io

    import qrcode

    try:
        image = qrcode.make(address.address)
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
    except Exception:  # noqa: BLE001 - QR failure must not break deposits
        return None


@dataclass
class SubmissionResult:
    deposit: Deposit


def get_network_minimum(network: Network) -> Decimal:
    """Effective minimum deposit for ``network`` (per-network override else global)."""
    if network.min_deposit is not None:
        return network.min_deposit
    return get_minimum_deposit()


def _validate_submission(*, user, network_code: str, amount, tx_hash: str, order_id: str) -> dict:
    """Validate a submission; raises DepositError with field errors."""
    errors: dict[str, list[str]] = {}

    network = Network.objects.filter(code=(network_code or '').strip().upper()).first()
    if network is None:
        errors.setdefault('network', []).append('Selected network is not supported.')
    elif not network.is_active:
        errors.setdefault('network', []).append('Selected network is currently unavailable.')
    elif network.asset != 'USDT':
        errors.setdefault('network', []).append('Only USDT deposits are supported.')

    try:
        amount_decimal = normalize_amount(amount)
    except WalletError as exc:
        errors.setdefault('amount', []).append(str(exc))
        amount_decimal = None

    minimum = None
    if amount_decimal is not None:
        network_for_min = Network.objects.filter(code=(network_code or '').strip().upper()).first()
        minimum = get_network_minimum(network_for_min) if network_for_min else get_minimum_deposit()
        if amount_decimal < minimum:
            errors.setdefault('amount', []).append(
                f'Minimum deposit is {minimum.quantize(Decimal("0.01"))} USDT.'
            )

    tx_hash = (tx_hash or '').strip()
    order_id = (order_id or '').strip()
    if not tx_hash and not order_id:
        errors.setdefault('tx_hash', []).append(
            'A transaction hash or order ID is required.'
        )

    if errors:
        raise DepositError('Please correct the highlighted fields.', errors)

    # Duplicate protection — per-user (friendly error) and GLOBAL: the same
    # tx hash may never sit in two active deposits, whichever user submitted
    # it. The DB constraint (deposit_unique_active_tx_hash) is the backstop.
    if tx_hash:
        if Deposit.objects.filter(
            user=user, network=network, tx_hash__iexact=tx_hash,
            status__in=[Deposit.Status.PENDING, Deposit.Status.APPROVED],
        ).exists():
            raise DepositError(
                'This transaction has already been submitted.',
                {'tx_hash': ['This transaction hash was already used in a pending or approved deposit.']},
            )
        if Deposit.objects.exclude(user=user).filter(
            tx_hash__iexact=tx_hash,
            status__in=[Deposit.Status.PENDING, Deposit.Status.APPROVED],
        ).exists():
            raise DepositError(
                'This transaction has already been submitted.',
                {'tx_hash': ['This transaction hash is already recorded on another deposit.']},
            )
    elif order_id and Deposit.objects.filter(
        user=user, order_id__iexact=order_id,
        status__in=[Deposit.Status.PENDING, Deposit.Status.APPROVED],
    ).exists():
        raise DepositError(
            'This order reference has already been submitted.',
            {'order_id': ['This order reference was already used in a pending or approved deposit.']},
        )

    address = get_active_address(network)
    if address is None:
        raise DepositError(
            'No active deposit address is available for this network. Please try another network.',
            {'network': ['No deposit address available for this network.']},
        )

    return {
        'network': network,
        'amount': amount_decimal,
        'tx_hash': tx_hash,
        'order_id': order_id,
        'address': address,
    }


@transaction.atomic
def submit_deposit(
    *, user, network_code: str, amount, tx_hash: str, order_id: str,
    screenshot=None,
) -> SubmissionResult:
    """Create a PENDING deposit. No wallet changes here, ever.

    ``screenshot`` is an optional validated upload (payment proof)."""
    # Server-side account-status gate (Section 14 §9): suspended/banned
    # accounts cannot submit deposits, regardless of what the UI shows.
    try:
        ensure_active(user)
    except AuthError as exc:
        raise DepositError(exc.message) from exc
    data = _validate_submission(
        user=user, network_code=network_code, amount=amount, tx_hash=tx_hash, order_id=order_id,
    )
    deposit = Deposit.objects.create(
        user=user,
        network=data['network'],
        asset=data['network'].asset,
        amount=data['amount'],
        tx_hash=data['tx_hash'],
        order_id=data['order_id'],
        deposit_address=data['address'].address,  # snapshot at submission time
        screenshot=screenshot,
        status=Deposit.Status.PENDING,
        submitted_at=timezone.now(),
    )
    notify_event(
        user=user,
        notification_type=Notification.NotificationType.DEPOSIT,
        title='Deposit Submitted',
        message='Your deposit request has been submitted for review.',
        event_key=f'deposit:{deposit.deposit_id}:submitted',
        related_type='deposit',
        related_id=deposit.deposit_id,
    )
    return SubmissionResult(deposit=deposit)


def approval_idempotency_key(deposit: Deposit) -> str:
    return f'DEPOSIT_APPROVAL_{deposit.pk}'


@transaction.atomic
def approve_deposit(*, deposit: Deposit, admin_user, note: str = '') -> Deposit:
    """Admin approval: mark approved + credit wallet + audit, atomically.

    Idempotent at two layers: the deposit row is re-read with a status
    guard, and the wallet service dedupes on ``DEPOSIT_APPROVAL_<pk>``.
    """
    # Lock the deposit row and re-check status inside the transaction.
    locked = Deposit.objects.select_for_update().get(pk=deposit.pk)
    if locked.status == Deposit.Status.APPROVED:
        return locked  # already credited — nothing to do
    if locked.status != Deposit.Status.PENDING:
        raise DepositError(f'Deposit {locked.deposit_id} is {locked.status.lower()} and cannot be approved.')

    ledger = credit(
        user=locked.user,
        amount=locked.amount,
        balance_type='DEPOSIT',
        transaction_type='DEPOSIT',
        reference_type='deposit',
        reference_id=locked.deposit_id,
        description=f'USDT deposit {locked.deposit_id} approved',
        idempotency_key=approval_idempotency_key(locked),
    )

    locked.status = Deposit.Status.APPROVED
    locked.approved_at = timezone.now()
    locked.reviewed_by = admin_user
    if note.strip():
        locked.admin_note = note.strip()[:2000]
    locked.save()

    AuditLog.objects.create(
        actor_user=admin_user,
        action=AuditLog.Action.APPROVE,
        target_type='deposit',
        target_id=locked.deposit_id,
        description=f'Approved {locked.amount} {locked.asset} deposit for {locked.user.user_id} (ledger {ledger.transaction_id}).',
    )
    notify_event(
        user=locked.user,
        notification_type=Notification.NotificationType.DEPOSIT,
        title='Deposit Approved',
        message=(
            f'Your deposit of {locked.amount} {locked.asset} has been approved '
            f'and credited to your account.'
        ),
        event_key=f'deposit:{locked.deposit_id}:approved',
        related_type='deposit',
        related_id=locked.deposit_id,
    )
    return locked


@transaction.atomic
def reject_deposit(*, deposit: Deposit, admin_user, reason: str) -> Deposit:
    """Admin rejection: no wallet changes, audit + notification only."""
    locked = Deposit.objects.select_for_update().get(pk=deposit.pk)
    if locked.status == Deposit.Status.REJECTED:
        return locked
    if locked.status != Deposit.Status.PENDING:
        raise DepositError(f'Deposit {locked.deposit_id} is {locked.status.lower()} and cannot be rejected.')
    if not reason:
        raise DepositError('A rejection reason is required.', {'reason': ['A reason is required.']})

    locked.status = Deposit.Status.REJECTED
    locked.rejected_at = timezone.now()
    locked.reviewed_by = admin_user
    locked.admin_note = reason[:2000]
    locked.save()

    AuditLog.objects.create(
        actor_user=admin_user,
        action=AuditLog.Action.REJECT,
        target_type='deposit',
        target_id=locked.deposit_id,
        description=f'Rejected {locked.amount} {locked.asset} deposit for {locked.user.user_id}: {reason}',
    )
    notify_event(
        user=locked.user,
        notification_type=Notification.NotificationType.DEPOSIT,
        title='Deposit Rejected',
        message=f'Your deposit of {locked.amount} {locked.asset} was rejected.\n\nReason: {reason}',
        event_key=f'deposit:{locked.deposit_id}:rejected',
        related_type='deposit',
        related_id=locked.deposit_id,
    )
    return locked
