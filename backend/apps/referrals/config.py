"""Referral configuration (Section 9 §11, §49).

Commission rates and the maximum referral depth come from the SiteSetting
key/value store (editable without a deploy) with coded fallback defaults so
a fresh environment works out of the box.

Rates are **percentages** stored as Decimal strings (e.g. '10' = 10%).
"""

from decimal import Decimal, InvalidOperation

from apps.core.models import SiteSetting

# SiteSetting keys.
KEY_LEVEL_RATE = 'referral.level_{level}_rate_percent'
KEY_MAX_LEVEL = 'referral.max_level'
KEY_SIGNUP_REWARD = 'referral.signup_reward'

# Coded fallback defaults — configuration only, never a promise of income.
DEFAULT_RATES = {
    1: Decimal('10'),   # 10%
    2: Decimal('5'),    # 5%
    3: Decimal('2'),    # 2%
}
DEFAULT_MAX_LEVEL = 3
HARD_MAX_LEVEL = 5   # engine bound regardless of configuration
# One-time reward paid to the referrer when a new member joins via their
# code (Issue 6). Exactly 1 USDT by default; SiteSetting-overridable.
DEFAULT_SIGNUP_REWARD = Decimal('1')

_RATE_CACHE: dict[int, Decimal] = {}
_MAX_LEVEL_CACHE: int | None = None
_SIGNUP_REWARD_CACHE: Decimal | None = None


def get_rate_for_level(level: int) -> Decimal:
    """Configured rate (percent) for a level, validated non-negative."""
    cached = _RATE_CACHE.get(level)
    if cached is not None:
        return cached
    raw = SiteSetting.objects.filter(key=KEY_LEVEL_RATE.format(level=level)).values_list('value', flat=True).first()
    rate = DEFAULT_RATES.get(level, Decimal('0'))
    if raw is not None:
        try:
            rate = Decimal(raw)
        except InvalidOperation:
            rate = DEFAULT_RATES.get(level, Decimal('0'))
    if rate < 0:
        rate = Decimal('0')
    _RATE_CACHE[level] = rate
    return rate


def get_max_level() -> int:
    """Configured maximum referral depth, bounded by HARD_MAX_LEVEL."""
    global _MAX_LEVEL_CACHE
    if _MAX_LEVEL_CACHE is not None:
        return _MAX_LEVEL_CACHE
    raw = SiteSetting.objects.filter(key=KEY_MAX_LEVEL).values_list('value', flat=True).first()
    value = DEFAULT_MAX_LEVEL
    if raw is not None:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = DEFAULT_MAX_LEVEL
    value = max(1, min(HARD_MAX_LEVEL, value))
    _MAX_LEVEL_CACHE = value
    return value


def get_signup_reward() -> Decimal:
    """Configured one-time signup reward for the referrer (Issue 6)."""
    global _SIGNUP_REWARD_CACHE
    if _SIGNUP_REWARD_CACHE is not None:
        return _SIGNUP_REWARD_CACHE
    raw = SiteSetting.objects.filter(key=KEY_SIGNUP_REWARD).values_list('value', flat=True).first()
    reward = DEFAULT_SIGNUP_REWARD
    if raw is not None:
        try:
            reward = Decimal(raw)
        except InvalidOperation:
            reward = DEFAULT_SIGNUP_REWARD
    if reward < 0:
        reward = Decimal('0')
    _SIGNUP_REWARD_CACHE = reward
    return reward


def rates_snapshot() -> dict[int, Decimal]:
    """All configured rates (1..max_level) for APIs/serializers."""
    return {level: get_rate_for_level(level) for level in range(1, get_max_level() + 1)}


def reset_cache() -> None:
    """Clear cached configuration (used by tests)."""
    global _MAX_LEVEL_CACHE, _SIGNUP_REWARD_CACHE
    _RATE_CACHE.clear()
    _MAX_LEVEL_CACHE = None
    _SIGNUP_REWARD_CACHE = None
