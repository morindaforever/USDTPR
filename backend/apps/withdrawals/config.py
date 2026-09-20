"""Withdrawal configuration (Section 10 §13–15, §46).

Fee and minimum-withdrawal rules come from SiteSetting keys with coded
defaults, so nothing is hard-coded in multiple files. The BACKEND is the
authoritative calculator — every API request is recomputed server-side.

Fee model: a single fixed fee (Decimal USDT, default 1.00), with '0'
meaning no fee. Percentage fees can be enabled by setting
``withdrawal.fee_type`` to ``PERCENT`` and ``withdrawal.fee_amount`` to the
percent value (e.g. '2' = 2%).
"""

from decimal import Decimal, InvalidOperation

from apps.core.models import SiteSetting

KEY_FEE_TYPE = 'withdrawal.fee_type'        # FIXED | PERCENT
KEY_FEE_AMOUNT = 'withdrawal.fee_amount'    # USDT (FIXED) or percent (PERCENT)
KEY_MIN_AMOUNT = 'withdrawal.min_amount'    # USDT

DEFAULT_FEE_TYPE = 'FIXED'
DEFAULT_FEE_AMOUNT = Decimal('1.00')
DEFAULT_MIN_AMOUNT = Decimal('5.00')

_fee_cache: dict[str, Decimal | str] = {}


def _get_setting(key: str, default: str) -> str:
    return (
        SiteSetting.objects.filter(key=key)
        .values_list('value', flat=True)
        .first()
        or default
    )


def _decimal(raw: str, fallback: Decimal) -> Decimal:
    try:
        value = Decimal(raw)
    except (InvalidOperation, TypeError):
        return fallback
    return value if value >= 0 else fallback


def invalidate_cache() -> None:
    """Clear cached config (used by tests and after admin edits)."""
    _fee_cache.clear()


def get_min_amount(network=None) -> Decimal:
    """Configured minimum withdrawal amount (§13).

    A per-network override (Network.min_withdrawal) wins; otherwise the
    global ``withdrawal.min_amount`` SiteSetting applies.
    """
    if network is not None and getattr(network, 'min_withdrawal', None) is not None:
        return network.min_withdrawal
    cached = _fee_cache.get('min')
    if cached is not None:
        return cached  # type: ignore[return-value]
    value = _decimal(_get_setting(KEY_MIN_AMOUNT, str(DEFAULT_MIN_AMOUNT)), DEFAULT_MIN_AMOUNT)
    _fee_cache['min'] = value
    return value


def get_fee_type(network=None) -> str:
    """'FIXED' or 'PERCENT' (per-network override wins)."""
    if network is not None and getattr(network, 'withdrawal_fee_is_percent', None) is not None:
        return 'PERCENT' if network.withdrawal_fee_is_percent else 'FIXED'
    cached = _fee_cache.get('type')
    if cached is not None:
        return str(cached)
    value = _get_setting(KEY_FEE_TYPE, DEFAULT_FEE_TYPE).upper()
    if value not in ('FIXED', 'PERCENT'):
        value = DEFAULT_FEE_TYPE
    _fee_cache['type'] = value
    return value


def get_fee_amount(network=None) -> Decimal:
    """Fee magnitude: USDT when FIXED, percent when PERCENT (per-network wins)."""
    if network is not None and getattr(network, 'withdrawal_fee', None) is not None:
        return network.withdrawal_fee
    cached = _fee_cache.get('amount')
    if cached is not None:
        return cached  # type: ignore[return-value]
    value = _decimal(_get_setting(KEY_FEE_AMOUNT, str(DEFAULT_FEE_AMOUNT)), DEFAULT_FEE_AMOUNT)
    _fee_cache['amount'] = value
    return value


def calculate_fee(amount: Decimal, network=None) -> Decimal:
    """Fee for ``amount`` per the configured rule (§14–15), Decimal only."""
    fee_type = get_fee_type(network)
    fee_amount = get_fee_amount(network)
    if fee_type == 'PERCENT':
        fee = (amount * fee_amount / Decimal('100'))
    else:
        fee = fee_amount
    # Never exceed the withdrawal itself (net can never go negative, §15).
    return min(fee, amount)


def calculate_net(amount: Decimal, network=None) -> tuple[Decimal, Decimal]:
    """Return ``(fee, net)`` for a requested amount."""
    fee = calculate_fee(amount, network).quantize(Decimal('0.00000001'))
    net = (amount - fee).quantize(Decimal('0.00000001'))
    return fee, net
