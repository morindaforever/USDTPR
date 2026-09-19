"""Referral-tree traversal (Section 9 §21, §76).

Team membership is derived by walking ``User.referred_by`` links upward from
a source user: the direct referrer is Level 1, their referrer Level 2, and so
on — bounded by the configured maximum level (§10). Walking up from the
source (instead of recursively expanding children) means every query is a
bounded ``N ≤ max_level`` lookup, never unbounded recursion.
"""

from apps.accounts.models import User

from . import config


def eligible_referrer(user) -> bool:
    """Whether ``user`` may receive commissions right now (§6, §40)."""
    return (
        user is not None
        and user.is_active
        and user.account_status == User.AccountStatus.ACTIVE
    )


def ancestors_with_levels(source_user) -> list[tuple[object, int, object]]:
    """Return ``[(ancestor, level, referral_row), …]`` from the source upward.

    - Bounded by ``config.get_max_level()`` (§10, §76).
    - Only ACTIVE relationships pay; the walk stops at the first non-ACTIVE
      row (a blocked relationship cuts the branch — historical rows stay
      intact, they just stop accruing).
    - Inactive/suspended/banned ancestors are skipped for commissions (§6)
      but do not sever deeper levels (the chain itself is intact).
    """
    results: list[tuple[object, int, object]] = []
    from .models import Referral

    current = source_user
    for level in range(1, config.get_max_level() + 1):
        referrer_id = current.referred_by_id
        if referrer_id is None:
            break
        try:
            referral = (
                Referral.objects.select_related('referrer')
                .get(referred_user_id=current.id, referrer_id=referrer_id)
            )
        except Referral.DoesNotExist:
            break
        if referral.status != Referral.Status.ACTIVE:
            break
        if eligible_referrer(referral.referrer):
            results.append((referral.referrer, level, referral))
        current = referral.referrer
    return results
