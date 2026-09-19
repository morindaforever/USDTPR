"""Referral commission engine (Section 9) — the ONLY way commissions are paid.

Architecture (§2, §18) — no direct wallet mutation anywhere here:

    VIP Reward Engine (Section 8, reward_service.process_reward)
        → on_referral_reward_credited(reward)      [this module]
            → tree.ancestors_with_levels(source)    (bounded walk)
                → per ancestor, atomic:
                    ReferralCommission (PENDING, snapshotted rate/level)
                    → wallet service credit()           (Section 5)
                        → wallet ledger row (REFERRAL_COMMISSION)
                        → wallet balance
                    → CREDITED + audit + notification
            → failures recorded per commission (FAILED), never fatal to
              the caller — one bad ancestor must not break the others.

Idempotency (§17): deterministic key ``REF_COMM_<reward_id>_<user>_<level>``
backed by a UNIQUE column. Retries, racing workers, and re-runs can never
pay a commission twice; the first CREDITED row wins and later calls observe
it and skip (§60).

Isolation (§19, §36): each ancestor is processed in its OWN atomic block —
a failed wallet credit for one level neither rolls back the source reward
nor blocks other levels. The source reward is never modified here.
Commissions are generated ONLY from VIP reward events — never from
registrations (§5), deposits (§37), withdrawals (§38), or other
commissions (§36).

All arithmetic is Decimal at wallet precision (§13, §14). Rates are loaded
from the config layer and SNAPSHOTTED onto the row (§15, §48).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.notifications.services import notify_event
from apps.wallet.models import WalletTransaction
from apps.wallet.services import WalletError, credit

from . import config, tree
from .models import ReferralCommission

logger = logging.getLogger('referrals.commissions')

QUANT = Decimal('0.00000001')


class CommissionError(Exception):
    """Domain error raised when a commission run fails wholesale."""


@dataclass(frozen=True)
class CommissionOutcome:
    user_id: str
    level: int
    status: str            # 'credited' | 'already_credited' | 'failed'
    amount: Decimal | None = None
    commission_id: str | None = None


def commission_idempotency_key(reward_id: str, beneficiary_pk, level: int) -> str:
    """Deterministic per (reward, beneficiary, level) — §17."""
    return f'REF_COMM_{reward_id}_{beneficiary_pk}_{level}'


def calculate_commission(amount: Decimal, rate_percent: Decimal) -> Decimal:
    """``amount × rate%`` in Decimal, quantized to wallet precision (§13)."""
    if rate_percent < 0:
        raise CommissionError('Commission rate must be non-negative.')
    return (amount * rate_percent / Decimal('100')).quantize(QUANT, rounding=ROUND_HALF_UP)


@transaction.atomic
def _credit_single(referral_commission: ReferralCommission) -> None:
    """Credit one PENDING commission; the caller owns failure recording."""
    txn = credit(
        user=referral_commission.user,
        amount=referral_commission.commission_amount,
        balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
        transaction_type=WalletTransaction.TransactionType.REFERRAL_COMMISSION,
        reference_type='referral_commission',
        reference_id=referral_commission.commission_id,
        description=(
            f'Referral commission — Level {referral_commission.level} '
            f'— from VIP reward ({referral_commission.source_user.user_id})'
        )[:255],
        idempotency_key=referral_commission.idempotency_key,
    )
    referral_commission.status = ReferralCommission.Status.CREDITED
    referral_commission.wallet_transaction = txn
    referral_commission.processed_at = timezone.now()
    referral_commission.save(update_fields=[
        'status', 'wallet_transaction', 'processed_at', 'updated_at',
    ])

    AuditLog.objects.create(
        actor_user=None,
        action=AuditLog.Action.OTHER,
        target_type='referral_commission',
        target_id=referral_commission.commission_id,            description=(
                f'Referral commission {referral_commission.commission_amount} USDT '
                f'(Level {referral_commission.level}) credited to '
                f'{referral_commission.user.user_id} from reward '
                f'{referral_commission.source_reward_id}.'
            ),
    )
    notify_event(
        user=referral_commission.user,
        notification_type=Notification.NotificationType.REFERRAL,
        title='Referral commission credited',
        message=(
            f'{referral_commission.commission_amount.quantize(Decimal("0.01"))} USDT '
            f'Level {referral_commission.level} commission has been credited to your wallet.'
        ),
        event_key=f'referral_commission:{referral_commission.commission_id}:credited',
        related_type='referral_commission',
        related_id=referral_commission.commission_id,
    )


def process_commission(
    *,
    beneficiary,
    level: int,
    referral,
    reward,
) -> CommissionOutcome:
    """Create + credit one commission for one ancestor (§18).

    Idempotent and concurrency-safe: the deterministic key plus the wallet
    service's own idempotency make duplicate payment impossible; a racing
    worker loses on the unique constraint and reports ``already_credited``.
    """
    key = commission_idempotency_key(reward.reward_id, beneficiary.pk, level)

    existing = ReferralCommission.objects.filter(idempotency_key=key).first()
    if existing is not None:
        if existing.status == ReferralCommission.Status.CREDITED:
            return CommissionOutcome(
                user_id=existing.user.user_id, level=level,
                status='already_credited', amount=existing.commission_amount,
                commission_id=existing.commission_id,
            )
        # PENDING/FAILED from an earlier crash — reclaim below.
        referral_commission = existing
    else:
        rate_percent = config.get_rate_for_level(level)
        amount = calculate_commission(reward.credited_amount, rate_percent)
        # Stored as a FRACTION (0.10 = 10%), matching the VIP daily-rate
        # convention and the column's (5, 4) precision.
        rate_fraction = (rate_percent / Decimal('100')).quantize(Decimal('0.0001'))
        try:
            referral_commission = ReferralCommission.objects.create(
                user=beneficiary,
                source_user=reward.user,
                referral=referral,
                level=level,
                source_reward=reward,
                source_reward_amount=reward.credited_amount,
                commission_rate=rate_fraction,
                commission_amount=amount,
                cycle_date=reward.reward_date,
                idempotency_key=key,
            )
        except IntegrityError:
            # Racing worker created it first; nothing to pay.
            return CommissionOutcome(
                user_id=beneficiary.user_id, level=level, status='already_credited',
            )

    try:
        _credit_single(referral_commission)
    except WalletError as exc:
        # Record the failure (committed by the outer atomic in process_reward
        # or standalone) — no money moved, the row stays for the audit trail.
        referral_commission.status = ReferralCommission.Status.FAILED
        referral_commission.error_info = (exc.message or 'wallet-credit-failed')[:255]
        referral_commission.processed_at = timezone.now()
        referral_commission.save(update_fields=[
            'status', 'error_info', 'processed_at', 'updated_at',
        ])
        AuditLog.objects.create(
            actor_user=None,
            action=AuditLog.Action.OTHER,
            target_type='referral_commission',
            target_id=referral_commission.commission_id,
            description=(
                f'Referral commission failed for reward {reward.reward_id} '
                f'(Level {level}, beneficiary {beneficiary.user_id}).'
            ),
        )
        logger.warning(
            'Commission credit failed reward=%s beneficiary=%s level=%s: %s',
            reward.reward_id, beneficiary.user_id, level, exc,
        )
        return CommissionOutcome(
            user_id=beneficiary.user_id, level=level, status='failed',
            commission_id=referral_commission.commission_id,
        )

    return CommissionOutcome(
        user_id=beneficiary.user_id, level=level, status='credited',
        amount=referral_commission.commission_amount,
        commission_id=referral_commission.commission_id,
    )


def on_referral_reward_credited(reward) -> list[CommissionOutcome]:
    """Entry point for the Section 8 reward engine (§18, §45).

    Called AFTER a reward is successfully credited (COMPLETED). Pays the
    configured ancestors of ``reward.user``; never raises — commission
    failures are recorded per ancestor and logged.
    """
    outcomes: list[CommissionOutcome] = []
    for beneficiary, level, referral in tree.ancestors_with_levels(reward.user):
        try:
            outcomes.append(
                process_commission(
                    beneficiary=beneficiary, level=level,
                    referral=referral, reward=reward,
                )
            )
        except Exception:  # noqa: BLE001 — one ancestor must not break the rest
            logger.exception(
                'Unexpected commission failure reward=%s level=%s',
                reward.reward_id, level,
            )
    if outcomes:
        logger.info(
            'Commissions for reward %s: %s',
            reward.reward_id,
            ', '.join(f'{o.user_id}:L{o.level}:{o.status}' for o in outcomes),
        )
    return outcomes


def process_referral_commission(reward_id: str, cycle_date: date | None = None) -> list[CommissionOutcome]:
    """Celery-task entry point (§46): pay commissions for a reward by ID.

    Verifies the reward is actually COMPLETED before paying (a FAILED or
    PENDING reward never generates commissions). ``cycle_date`` is accepted
    for API compatibility with the reward engine's cycle handling.
    """
    from apps.vip.models import VIPReward

    reward = VIPReward.objects.select_related('user').filter(reward_id=reward_id).first()
    if reward is None:
        raise CommissionError(f'Reward {reward_id} not found.')
    if reward.status != VIPReward.Status.COMPLETED:
        raise CommissionError(f'Reward {reward_id} is not COMPLETED ({reward.status}).')
    return on_referral_reward_credited(reward)
