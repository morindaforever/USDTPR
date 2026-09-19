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

from django.db import transaction

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.notifications.models import Notification

from . import config
from .models import Referral


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
    return RelationshipResult(referral=referral, created=True)
