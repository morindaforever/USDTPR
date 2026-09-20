"""Centralized wallet service — the ONLY way balances may change.

Every future module (deposits, withdrawals, VIP, referrals, admin) must call
these functions instead of writing ``Wallet`` columns directly.

FLOW (ledger-first, all inside one database transaction)::

    validate → BEGIN ATOMIC → lock wallet row (select_for_update)
             → idempotency check → insufficient-balance checks
             → create ledger row(s) → update wallet buckets → COMMIT

ACCOUNTING RULES
----------------
- ``total_balance`` is a derived display aggregate maintained here:
  total = deposit + withdrawable + bonus + locked + pending. Operations
  never credit/debit TOTAL directly — they move real buckets and total is
  recomputed. (This makes the invariant impossible to violate.)
- Only COMPLETED ledger rows affect balances. PENDING ledger rows may be
  created by callers (e.g. a withdrawal request) with NO balance effect;
  completing them later is a separate explicit operation.
- Lock/release/finalize move funds between buckets; each affected bucket
  gets its own ledger row so every balance change has an audit entry.
- Idempotency: when ``idempotency_key`` is supplied and a COMPLETED row with
  the same key exists, the operation returns that existing transaction and
  does NOT move money again. (Race fallback: the unique constraint on
  ``idempotency_key`` raises DuplicateTransactionError on a true conflict.)
- Concurrency: wallet rows are always locked with ``select_for_update``
  inside ``transaction.atomic`` so two concurrent debits cannot both spend
  the same balance.

All amounts are ``decimal.Decimal`` — never float — at 8 decimal places.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Case, Count, DecimalField, F, Q, Sum, When

from apps.core.models import AuditLog

from ..models import Wallet, WalletTransaction
from .errors import (
    DuplicateTransactionError,
    InsufficientBalanceError,
    InvalidAmountError,
    InvalidBalanceTypeError,
    InvalidTransactionError,
    WalletNotFoundError,
)

# Balance buckets that may be directly credited/debited. TOTAL is excluded:
# it is recomputed from the buckets after every operation.
CREDITABLE_BALANCE_TYPES = {
    WalletTransaction.BalanceType.DEPOSIT,
    WalletTransaction.BalanceType.WITHDRAWABLE,
    WalletTransaction.BalanceType.BONUS,
    WalletTransaction.BalanceType.PENDING,
    WalletTransaction.BalanceType.LOCKED,
}
DEBITABLE_BALANCE_TYPES = {
    WalletTransaction.BalanceType.DEPOSIT,
    WalletTransaction.BalanceType.WITHDRAWABLE,
    WalletTransaction.BalanceType.BONUS,
    # PENDING/LOCKED may be debited only by explicit lock-release flows.
    WalletTransaction.BalanceType.PENDING,
    WalletTransaction.BalanceType.LOCKED,
}

# Buckets ``debit_across`` may spend: the free-to-spend buckets. LOCKED is
# excluded on purpose — it is reserved for in-flight withdrawals, and letting
# purchases drain it would double-spend reserved funds. PENDING likewise.
SPENDABLE_BALANCE_TYPES = {
    WalletTransaction.BalanceType.DEPOSIT,
    WalletTransaction.BalanceType.WITHDRAWABLE,
    WalletTransaction.BalanceType.BONUS,
}

QUANT = Decimal('0.00000001')


def normalize_amount(amount) -> Decimal:
    """Coerce str/int/Decimal amounts into an 8-dp Decimal; reject garbage.

    Floats are deliberately rejected: converting ``0.1`` through binary
    floating point can introduce error, so callers must pass Decimals,
    strings, or ints.
    """
    if isinstance(amount, float):
        raise InvalidAmountError('Amount must be provided as Decimal or string, not float.')
    try:
        value = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidAmountError('Amount is not a valid number.') from exc
    if not value.is_finite():
        raise InvalidAmountError('Amount must be a finite number.')
    if value <= 0:
        raise InvalidAmountError('Amount must be greater than zero.')
    return value.quantize(QUANT)


def _balance_type(value) -> WalletTransaction.BalanceType:
    try:
        return WalletTransaction.BalanceType(value)
    except ValueError as exc:
        raise InvalidBalanceTypeError(f'Unknown balance type: {value!r}') from exc


def get_wallet(user) -> Wallet:
    """Return the user's wallet or raise WalletNotFoundError.

    Callers who need repair behavior use ``ensure_wallet`` explicitly —
    request paths must not silently create rows.
    """
    wallet = Wallet.objects.filter(user=user).first()
    if wallet is None:
        raise WalletNotFoundError()
    return wallet


@transaction.atomic
def ensure_wallet(user) -> Wallet:
    """Repair mechanism: create the wallet if (and only if) missing.

    One user ↔ one wallet is enforced by the unique FK constraint; the
    ``get_or_create`` is race-safe.
    """
    wallet, created = Wallet.objects.get_or_create(user=user)
    return wallet


def get_wallet_summary(user) -> dict:
    """Read-only snapshot of all buckets (Decimal → string serialization
    happens in the API layer; this returns Decimals)."""
    wallet = get_wallet(user)
    return {
        'total_balance': wallet.total_balance,
        'deposit_balance': wallet.deposit_balance,
        'withdrawable_balance': wallet.withdrawable_balance,
        'pending_balance': wallet.pending_balance,
        'locked_balance': wallet.locked_balance,
        'bonus_balance': wallet.bonus_balance,
    }


def _find_idempotent(user, idempotency_key: str | None) -> WalletTransaction | None:
    if not idempotency_key:
        return None
    return WalletTransaction.objects.filter(
        user=user, idempotency_key=idempotency_key, status=WalletTransaction.Status.COMPLETED,
    ).first()


def _lock_wallet(user) -> Wallet:
    """SELECT ... FOR UPDATE on the wallet row; must run inside atomic."""
    wallet = Wallet.objects.select_for_update().filter(user=user).first()
    if wallet is None:
        raise WalletNotFoundError()
    return wallet


def _recompute_total(wallet: Wallet) -> None:
    wallet.total_balance = (
        wallet.deposit_balance
        + wallet.withdrawable_balance
        + wallet.bonus_balance
        + wallet.locked_balance
        + wallet.pending_balance
    ).quantize(QUANT)


def _apply(wallet: Wallet, balance_type: WalletTransaction.BalanceType, direction: str, amount: Decimal) -> None:
    """Apply a delta to one bucket, enforcing the non-negative constraint."""
    field = f'{balance_type.value.lower()}_balance'
    current = getattr(wallet, field)
    updated = (current + amount) if direction == WalletTransaction.Direction.CREDIT else (current - amount)
    if updated < 0:
        raise InsufficientBalanceError(
            f'Insufficient {balance_type.label.lower()} balance: has {current.quantize(QUANT)}, needs {amount}.'
        )
    setattr(wallet, field, updated.quantize(QUANT))


def _make_ledger(
    *,
    user,
    txn_type: str,
    direction: str,
    balance_type: WalletTransaction.BalanceType,
    amount: Decimal,
    description: str = '',
    reference_type: str = '',
    reference_id: str = '',
    idempotency_key: str | None = None,
    status: str = WalletTransaction.Status.COMPLETED,
) -> WalletTransaction:
    try:
        return WalletTransaction.objects.create(
            user=user,
            transaction_type=txn_type,
            direction=direction,
            balance_type=balance_type,
            amount=amount,
            description=description[:255],
            reference_type=reference_type[:64],
            reference_id=reference_id[:64],
            idempotency_key=idempotency_key or None,
            status=status,
        )
    except IntegrityError as exc:
        # Race fallback: two workers grabbed the same idempotency key at
        # once; the unique constraint stops the second insert.
        raise DuplicateTransactionError() from exc


@transaction.atomic
def credit(
    *,
    user,
    amount,
    balance_type,
    transaction_type,
    reference_type: str = '',
    reference_id: str = '',
    description: str = '',
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """Credit a bucket atomically with its COMPLETED ledger row.

    Idempotent: re-running with the same ``idempotency_key`` returns the
    original transaction without moving money.
    """
    amount = normalize_amount(amount)
    balance_type = _balance_type(balance_type)
    if balance_type not in CREDITABLE_BALANCE_TYPES:
        raise InvalidBalanceTypeError(f'{balance_type.label} cannot be credited directly.')

    existing = _find_idempotent(user, idempotency_key)
    if existing is not None:
        return existing

    wallet = _lock_wallet(user)
    ledger = _make_ledger(
        user=user,
        txn_type=transaction_type,
        direction=WalletTransaction.Direction.CREDIT,
        balance_type=balance_type,
        amount=amount,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    _apply(wallet, balance_type, WalletTransaction.Direction.CREDIT, amount)
    _recompute_total(wallet)
    wallet.save()
    return ledger


@transaction.atomic
def debit(
    *,
    user,
    amount,
    balance_type,
    transaction_type,
    reference_type: str = '',
    reference_id: str = '',
    description: str = '',
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """Debit a bucket atomically with its COMPLETED ledger row.

    Raises InsufficientBalanceError (wallet untouched, no COMPLETED row)
    when funds are short. Row-level lock prevents concurrent double-spend.
    """
    amount = normalize_amount(amount)
    balance_type = _balance_type(balance_type)
    if balance_type not in DEBITABLE_BALANCE_TYPES:
        raise InvalidBalanceTypeError(f'{balance_type.label} cannot be debited directly.')

    existing = _find_idempotent(user, idempotency_key)
    if existing is not None:
        return existing

    wallet = _lock_wallet(user)
    # Pre-check gives a clean domain error; _apply re-checks under the lock.
    field = f'{balance_type.value.lower()}_balance'
    if getattr(wallet, field) < amount:
        raise InsufficientBalanceError(
            f'Insufficient {balance_type.label.lower()} balance: has '
            f'{getattr(wallet, field).quantize(QUANT)}, needs {amount}.'
        )
    ledger = _make_ledger(
        user=user,
        txn_type=transaction_type,
        direction=WalletTransaction.Direction.DEBIT,
        balance_type=balance_type,
        amount=amount,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    _apply(wallet, balance_type, WalletTransaction.Direction.DEBIT, amount)
    _recompute_total(wallet)
    wallet.save()
    return ledger


@transaction.atomic
def debit_across(
    *,
    user,
    amount,
    balance_types,
    transaction_type,
    reference_type: str = '',
    reference_id: str = '',
    description: str = '',
    idempotency_key: str | None = None,
) -> list[WalletTransaction]:
    """Debit one amount across several buckets, in order, atomically.

    Each bucket is drained up to ``amount`` before moving to the next, so a
    purchase can spend e.g. deposit balance first and fall back to the
    withdrawable bucket. One DEBIT ledger row is written per bucket touched
    (the first leg carries the caller's idempotency key verbatim, later legs
    get ``:b2``/``:b3`` suffixes, mirroring the lock/release convention).

    All-or-nothing: the combined balance is checked under the wallet row
    lock BEFORE any ledger row is written — if the buckets together cannot
    cover the amount, InsufficientBalanceError is raised with no money
    moved. Concurrency-safe for the same reason as ``debit``: competitors
    serialize on the row lock and re-check against post-debit balances.
    """
    amount = normalize_amount(amount)
    types = [_balance_type(value) for value in balance_types]
    if not types:
        raise InvalidBalanceTypeError('At least one balance type is required.')
    if len(set(types)) != len(types):
        raise InvalidBalanceTypeError('Balance types must not repeat.')
    for balance_type in types:
        if balance_type not in SPENDABLE_BALANCE_TYPES:
            raise InvalidBalanceTypeError(f'{balance_type.label} is not a spendable bucket.')

    existing = _find_idempotent(user, idempotency_key)
    if existing is not None:
        return [existing]

    wallet = _lock_wallet(user)
    # Combined affordability check under the lock, before any ledger write.
    combined = sum((getattr(wallet, f'{t.value.lower()}_balance') for t in types), Decimal('0'))
    if combined < amount:
        raise InsufficientBalanceError(
            f'Insufficient combined balance: has {combined.quantize(QUANT)}, needs {amount}.'
        )

    # Split the amount across buckets: drain each until the remainder is 0.
    remainder = amount
    legs: list[tuple[WalletTransaction.BalanceType, Decimal]] = []
    for balance_type in types:
        if remainder <= 0:
            break
        available = getattr(wallet, f'{balance_type.value.lower()}_balance')
        take = available if available < remainder else remainder
        if take > 0:
            legs.append((balance_type, take.quantize(QUANT)))
            remainder = (remainder - take).quantize(QUANT)

    ledgers: list[WalletTransaction] = []
    for index, (balance_type, take) in enumerate(legs):
        leg_key = idempotency_key if index == 0 else (
            f'{idempotency_key}:b{index + 1}' if idempotency_key else None
        )
        ledgers.append(_make_ledger(
            user=user,
            txn_type=transaction_type,
            direction=WalletTransaction.Direction.DEBIT,
            balance_type=balance_type,
            amount=take,
            description=description,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=leg_key,
        ))
        _apply(wallet, balance_type, WalletTransaction.Direction.DEBIT, take)
    _recompute_total(wallet)
    wallet.save()
    return ledgers


@transaction.atomic
def lock(
    *,
    user,
    amount,
    reference_type: str = '',
    reference_id: str = '',
    description: str = '',
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """Move withdrawable → locked (e.g. a pending withdrawal reservation).

    Two ledger rows (DEBIT withdrawable, CREDIT locked) under the caller's
    idempotency key, suffixed ':d'/':c' for the two legs.
    """
    amount = normalize_amount(amount)
    existing = _find_idempotent(user, idempotency_key)
    if existing is not None:
        return existing

    wallet = _lock_wallet(user)
    if wallet.withdrawable_balance < amount:
        raise InsufficientBalanceError(
            f'Insufficient withdrawable balance: has {wallet.withdrawable_balance.quantize(QUANT)}, needs {amount}.'
        )
    ledger = _make_ledger(
        user=user,
        txn_type=WalletTransaction.TransactionType.LOCK,
        direction=WalletTransaction.Direction.DEBIT,
        balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
        amount=amount,
        description=description or 'Funds locked',
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    _make_ledger(
        user=user,
        txn_type=WalletTransaction.TransactionType.LOCK,
        direction=WalletTransaction.Direction.CREDIT,
        balance_type=WalletTransaction.BalanceType.LOCKED,
        amount=amount,
        description=description or 'Funds locked',
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=f'{idempotency_key}:c' if idempotency_key else None,
    )
    _apply(wallet, WalletTransaction.BalanceType.WITHDRAWABLE, WalletTransaction.Direction.DEBIT, amount)
    _apply(wallet, WalletTransaction.BalanceType.LOCKED, WalletTransaction.Direction.CREDIT, amount)
    _recompute_total(wallet)
    wallet.save()
    return ledger


@transaction.atomic
def release_lock(
    *,
    user,
    amount,
    reference_type: str = '',
    reference_id: str = '',
    description: str = '',
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """Move locked → withdrawable (e.g. withdrawal rejected/cancelled)."""
    amount = normalize_amount(amount)
    existing = _find_idempotent(user, idempotency_key)
    if existing is not None:
        return existing

    wallet = _lock_wallet(user)
    if wallet.locked_balance < amount:
        raise InsufficientBalanceError(
            f'Insufficient locked balance: has {wallet.locked_balance.quantize(QUANT)}, needs {amount}.'
        )
    ledger = _make_ledger(
        user=user,
        txn_type=WalletTransaction.TransactionType.RELEASE,
        direction=WalletTransaction.Direction.DEBIT,
        balance_type=WalletTransaction.BalanceType.LOCKED,
        amount=amount,
        description=description or 'Lock released',
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    _make_ledger(
        user=user,
        txn_type=WalletTransaction.TransactionType.RELEASE,
        direction=WalletTransaction.Direction.CREDIT,
        balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
        amount=amount,
        description=description or 'Lock released',
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=f'{idempotency_key}:c' if idempotency_key else None,
    )
    _apply(wallet, WalletTransaction.BalanceType.LOCKED, WalletTransaction.Direction.DEBIT, amount)
    _apply(wallet, WalletTransaction.BalanceType.WITHDRAWABLE, WalletTransaction.Direction.CREDIT, amount)
    _recompute_total(wallet)
    wallet.save()
    return ledger


@transaction.atomic
def finalize_locked(
    *,
    user,
    amount,
    transaction_type=WalletTransaction.TransactionType.WITHDRAWAL,
    reference_type: str = '',
    reference_id: str = '',
    description: str = '',
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """Complete an operation whose funds are locked: locked → paid out.

    The locked bucket is debited; no other bucket gains. The future
    withdrawal module calls this after a successful payout, then marks its
    own object complete.
    """
    amount = normalize_amount(amount)
    existing = _find_idempotent(user, idempotency_key)
    if existing is not None:
        return existing

    wallet = _lock_wallet(user)
    if wallet.locked_balance < amount:
        raise InsufficientBalanceError(
            f'Insufficient locked balance: has {wallet.locked_balance.quantize(QUANT)}, needs {amount}.'
        )
    ledger = _make_ledger(
        user=user,
        txn_type=transaction_type,
        direction=WalletTransaction.Direction.DEBIT,
        balance_type=WalletTransaction.BalanceType.LOCKED,
        amount=amount,
        description=description or 'Locked funds finalized',
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    _apply(wallet, WalletTransaction.BalanceType.LOCKED, WalletTransaction.Direction.DEBIT, amount)
    _recompute_total(wallet)
    wallet.save()
    return ledger


@transaction.atomic
def transfer_between_balances(
    *,
    user,
    amount,
    from_balance_type,
    to_balance_type,
    reference_type: str = '',
    reference_id: str = '',
    description: str = '',
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """Move funds between two buckets of the same wallet."""
    amount = normalize_amount(amount)
    from_balance_type = _balance_type(from_balance_type)
    to_balance_type = _balance_type(to_balance_type)
    if from_balance_type == to_balance_type:
        raise InvalidBalanceTypeError('Source and destination balance types must differ.')
    if from_balance_type == WalletTransaction.BalanceType.TOTAL or to_balance_type == WalletTransaction.BalanceType.TOTAL:
        raise InvalidBalanceTypeError('TOTAL is derived and cannot be a transfer endpoint.')

    existing = _find_idempotent(user, idempotency_key)
    if existing is not None:
        return existing

    wallet = _lock_wallet(user)
    field = f'{from_balance_type.value.lower()}_balance'
    if getattr(wallet, field) < amount:
        raise InsufficientBalanceError(
            f'Insufficient {from_balance_type.label.lower()} balance: has '
            f'{getattr(wallet, field).quantize(QUANT)}, needs {amount}.'
        )
    ledger = _make_ledger(
        user=user,
        txn_type=WalletTransaction.TransactionType.TRANSFER,
        direction=WalletTransaction.Direction.DEBIT,
        balance_type=from_balance_type,
        amount=amount,
        description=description or f'Transfer to {to_balance_type.label.lower()}',
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    _make_ledger(
        user=user,
        txn_type=WalletTransaction.TransactionType.TRANSFER,
        direction=WalletTransaction.Direction.CREDIT,
        balance_type=to_balance_type,
        amount=amount,
        description=description or f'Transfer from {from_balance_type.label.lower()}',
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=f'{idempotency_key}:c' if idempotency_key else None,
    )
    _apply(wallet, from_balance_type, WalletTransaction.Direction.DEBIT, amount)
    _apply(wallet, to_balance_type, WalletTransaction.Direction.CREDIT, amount)
    _recompute_total(wallet)
    wallet.save()
    return ledger


@transaction.atomic
def admin_adjust(
    *,
    user,
    amount,
    balance_type,
    direction,
    reason: str,
    actor_user=None,
    request=None,
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """Privileged manual adjustment (future admin module uses this).

    Writes the ADJUSTMENT ledger row AND an AuditLog entry — an admin can
    never silently change balances. Must be invoked from admin-authorized
    code; it is not exposed on any user-facing API.
    """
    amount = normalize_amount(amount)
    balance_type = _balance_type(balance_type)
    if direction not in {WalletTransaction.Direction.CREDIT, WalletTransaction.Direction.DEBIT}:
        raise InvalidTransactionError('Direction must be CREDIT or DEBIT.')
    if not reason or not reason.strip():
        raise InvalidTransactionError('A reason is required for manual adjustments.')

    existing = _find_idempotent(user, idempotency_key)
    if existing is not None:
        return existing

    wallet = _lock_wallet(user)
    ledger = _make_ledger(
        user=user,
        txn_type=WalletTransaction.TransactionType.ADJUSTMENT,
        direction=direction,
        balance_type=balance_type,
        amount=amount,
        description=f'Admin adjustment: {reason}',
        reference_type='admin_adjustment',
        reference_id='',
        idempotency_key=idempotency_key,
    )
    _apply(wallet, balance_type, direction, amount)
    _recompute_total(wallet)
    wallet.save()

    AuditLog.objects.create(
        actor_user=actor_user,
        action=AuditLog.Action.ADJUST,
        target_type='wallet',
        target_id=str(wallet.pk),
        description=f'{direction} {amount} USDT to {balance_type.label.lower()}: {reason}',
        ip_address=None,
        user_agent='',
    )
    return ledger


@transaction.atomic
def reverse_transaction(
    *,
    ledger: WalletTransaction,
    reason: str,
    actor_user=None,
    idempotency_key: str | None = None,
) -> WalletTransaction:
    """Reverse a COMPLETED transaction by posting the opposite movement.

    The original row is marked REVERSED (history preserved); a new opposite
    row references it — money is never edited in place.
    """
    if ledger.status != WalletTransaction.Status.COMPLETED:
        raise InvalidTransactionError('Only COMPLETED transactions can be reversed.')
    if not reason or not reason.strip():
        raise InvalidTransactionError('A reason is required for reversals.')

    existing = _find_idempotent(ledger.user, idempotency_key)
    if existing is not None:
        return existing

    wallet = _lock_wallet(ledger.user)
    opposite = (
        WalletTransaction.Direction.DEBIT
        if ledger.direction == WalletTransaction.Direction.CREDIT
        else WalletTransaction.Direction.CREDIT
    )
    reversal = _make_ledger(
        user=ledger.user,
        txn_type=ledger.transaction_type,
        direction=opposite,
        balance_type=WalletTransaction.BalanceType(ledger.balance_type),
        amount=ledger.amount,
        description=f'Reversal of {ledger.transaction_id}: {reason}',
        reference_type=ledger.reference_type or 'wallet_transaction',
        reference_id=ledger.transaction_id,
        idempotency_key=idempotency_key,
    )
    _apply(wallet, WalletTransaction.BalanceType(ledger.balance_type), opposite, ledger.amount)
    _recompute_total(wallet)
    wallet.save()
    ledger.status = WalletTransaction.Status.REVERSED
    ledger.save(update_fields=['status'])
    return reversal


# --------------------------------------------------------------------------- #
# Reconciliation
# --------------------------------------------------------------------------- #
def reconcile_wallet(user) -> dict:
    """Compare wallet buckets against the ledger; report, never auto-fix.

    The per-bucket expectation sums COMPLETED ledger rows of each balance
    type (credits − debits). Lock/transfer pairs cancel per bucket, so the
    identity should hold exactly; deviations mean a code path bypassed the
    service and must be investigated by a human.
    """
    wallet = get_wallet(user)
    completed = WalletTransaction.objects.filter(
        user=user, status=WalletTransaction.Status.COMPLETED,
    )
    # Direction-aware sum per bucket: credits add, debits subtract.
    signed = Case(
        When(direction=WalletTransaction.Direction.CREDIT, then=F('amount')),
        When(direction=WalletTransaction.Direction.DEBIT, then=-F('amount')),
        output_field=DecimalField(max_digits=24, decimal_places=8),
    )
    sums = {
        row['balance_type']: row['total']
        for row in completed.annotate(signed=signed).values('balance_type').annotate(total=Sum('signed'))
    }

    issues: list[str] = []
    ledger_vs_wallet = {}
    for balance_type in WalletTransaction.BalanceType:
        if balance_type == WalletTransaction.BalanceType.TOTAL:
            continue
        field = f'{balance_type.value.lower()}_balance'
        expected = (sums.get(balance_type.value) or Decimal('0')).quantize(QUANT)
        actual = getattr(wallet, field).quantize(QUANT)
        ledger_vs_wallet[balance_type.value] = {'ledger': str(expected), 'wallet': str(actual)}
        if expected != actual:
            issues.append(f'{balance_type.value}: wallet={actual} ledger-sum={expected}')

    # Derived-total invariant check.
    bucket_sum = (
        wallet.deposit_balance + wallet.withdrawable_balance + wallet.bonus_balance
        + wallet.locked_balance + wallet.pending_balance
    ).quantize(QUANT)
    if bucket_sum != wallet.total_balance.quantize(QUANT):
        issues.append(f'TOTAL: wallet={wallet.total_balance.quantize(QUANT)} bucket-sum={bucket_sum}')

    # Structural checks: duplicate idempotency keys and odd states.
    dupes = (
        WalletTransaction.objects.filter(user=user, idempotency_key__isnull=False)
        .values('idempotency_key')
        .annotate(n=Count('id'))
    )
    for row in dupes:
        if row['n'] > 1:
            issues.append(f"duplicate idempotency_key {row['idempotency_key']} ({row['n']} rows)")

    bad_states = WalletTransaction.objects.filter(
        Q(user=user),
        Q(amount__lte=0) | Q(direction__isnull=True) | Q(balance_type__isnull=True),
    ).count()
    if bad_states:
        issues.append(f'{bad_states} transaction(s) with invalid amount/direction/balance_type')

    return {
        'user_id': getattr(user, 'user_id', str(user)),
        'ok': not issues,
        'issues': issues,
        'ledger_vs_wallet': ledger_vs_wallet,
    }


__all__ = [
    'admin_adjust',
    'credit',
    'debit',
    'debit_across',
    'ensure_wallet',
    'finalize_locked',
    'get_wallet',
    'get_wallet_summary',
    'lock',
    'normalize_amount',
    'reconcile_wallet',
    'release_lock',
    'reverse_transaction',
    'transfer_between_balances',
]
