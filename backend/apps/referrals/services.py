"""Referral relationship service (Section 9 §6, §8, §22).

Every referral relationship is created through :func:`create_relationship` —
signup, admin tooling, or any future flow — so the invariants hold in one
place:

- the referrer's account is ACTIVE (suspended/banned users cannot recruit);
- a user has at most ONE direct referrer (OneToOne constraint + explicit
  friendly error);
- no self-referral and no cycles (the would-be referrer must not be
  downstream of the new member).
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.wallet.models import WalletTransaction

from . import config
from .models import Referral

import logging

logger = logging.getLogger('referrals.signup_reward')


class ReferralError(Exception):
    """Referral relationship rejected with a user-safe message."""

    def __init__(self, message: str, field: str = 'referral_code') -> None:
        super().__init__(message)
        self.message = message
        self.field = field


@dataclass(frozen=True)
class RelationshipResult:
    referral: Referral
    created: bool


def _would_create_cycle(referrer: User, referred_user: User) -> bool:
    """True if ``referrer`` is reachable upward from ``referred_user``.

    Bounded by the configured max level (and HARD_MAX_LEVEL as a backstop),
    so even a corrupted chain cannot loop forever (§22, §76).
    """
    from . import tree

    depth = 0
    current = referrer
    bound = min(config.get_max_level(), tree.config.HARD_MAX_LEVEL) + 1
    while current.referred_by_id is not None and depth < bound:
        if current.referred_by_id == referred_user.id:
            return True
        current = current.referred_by
        depth += 1
    return False


@transaction.atomic
def create_relationship(*, referrer: User, referred_user: User) -> RelationshipResult:
    """Validate and create the referrer → referred_user relationship.

    Idempotent: if the same relationship already exists it is returned with
    ``created=False``; a DIFFERENT referrer for the same user is rejected
    (§8 — the first valid relationship stays authoritative).
    """
    if referrer.id == referred_user.id:
        raise ReferralError('A user cannot refer themselves.')

    existing = Referral.objects.filter(referred_user=referred_user).select_related('referrer').first()
    if existing is not None:
        if existing.referrer_id == referrer.id:
            return RelationshipResult(referral=existing, created=False)
        raise ReferralError('This user already has a referrer.')

    if referrer.account_status != User.AccountStatus.ACTIVE or not referrer.is_active:
        raise ReferralError('This referral code is not available.')

    if _would_create_cycle(referrer, referred_user):
        raise ReferralError('This referral would create a circular team structure.')

    referral = Referral.objects.create(referrer=referrer, referred_user=referred_user)

    AuditLog.objects.create(
        actor_user=referred_user,
        action=AuditLog.Action.OTHER,
        target_type='referral',
        target_id=str(referral.pk),
        description=f'Referral relationship created: {referrer.user_id} -> {referred_user.user_id}.',
    )
    Notification.objects.create(
        user=referrer,
        notification_type=Notification.NotificationType.REFERRAL,
        title='New team member',
        message=f'A new user has joined your Level 1 team ({referred_user.user_id}).',
    )
    _credit_signup_reward(referrer=referrer, referred_user=referred_user)
    return RelationshipResult(referral=referral, created=True)


def _credit_signup_reward(*, referrer: User, referred_user: User) -> None:
    """One-time signup reward to the referrer (Issue 6).

    Paid through the EXISTING wallet ledger service — never a direct balance
    write — as a REFERRAL_REWARD transaction credited to the referrer's
    withdrawable balance (the same bucket referral commissions use).

    Exactly once: the ledger idempotency key ``REFERRAL_REWARD_<user_id>`` is
    globally unique, so a retried or replayed relationship creation can never
    pay twice; ``create_relationship`` itself is idempotent and returns early
    when the relationship already exists.

    Non-fatal: a wallet failure must never block the new member's signup,
    mirroring the per-ancestor isolation of the commission engine. The
    failure is logged; the relationship stands.
    """
    from apps.notifications.services import notify_event
    from apps.wallet.services import WalletError, credit

    reward = config.get_signup_reward().quantize(Decimal('0.00000001'))
    if reward <= 0:
        return
    try:
        credit(
            user=referrer,
            amount=reward,
            balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
            transaction_type=WalletTransaction.TransactionType.REFERRAL_REWARD,
            reference_type='referral',
            reference_id=str(referred_user.pk),
            description=f'Referral signup reward — {referred_user.user_id} joined your team',
            idempotency_key=f'REFERRAL_REWARD_{referred_user.pk}',
        )
    except WalletError:
        logger.exception(
            'Referral signup reward failed referrer=%s referred=%s',
            referrer.pk, referred_user.pk,
        )
        return
    AuditLog.objects.create(
        actor_user=None,
        action=AuditLog.Action.OTHER,
        target_type='referral_reward',
        target_id=str(referred_user.pk),
        description=(
            f'Referral signup reward {reward} USDT credited to {referrer.user_id} '
            f'for new member {referred_user.user_id}.'
        ),
    )
    notify_event(
        user=referrer,
        notification_type=Notification.NotificationType.REFERRAL,
        title='Referral signup reward',
        message=(
            f'{reward.quantize(Decimal("0.01"))} USDT referral signup reward credited — '
            f'{referred_user.user_id} joined your team.'
        ),
        event_key=f'referral_reward:{referred_user.pk}',
        related_type='user',
        related_id=str(referred_user.pk),
    )
