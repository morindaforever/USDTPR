"""Network-aware destination-address FORMAT validation (Section 10 §10).

This is FORMAT validation only — it does not and cannot verify that an
address exists on-chain or is controlled by the user. The UI labels it
accordingly. Patterns are intentionally conservative: when a network's
address format is not reliably checkable, only length/charset rules apply.
"""

import re

# Per-network address rules. Order matters for regexes with alternation.
_EVM_RE = re.compile(r'^0x[0-9a-fA-F]{40}$')
_TRON_RE = re.compile(r'^T[1-9A-HJ-NP-Za-km-z]{33}$')
_SOL_RE = re.compile(r'^[1-9A-HJ-NP-Za-km-z]{32,44}$')
_TON_RE = re.compile(r'^(?:EQ|UQ)[0-9A-Za-z_-]{46}$')

NETWORK_RULES: dict[str, dict] = {
    'BSC': {'label': 'BNB Smart Chain', 'pattern': _EVM_RE, 'hint': '0x… 42-character hex address'},
    'ETH': {'label': 'Ethereum', 'pattern': _EVM_RE, 'hint': '0x… 42-character hex address'},
    'POL': {'label': 'Polygon', 'pattern': _EVM_RE, 'hint': '0x… 42-character hex address'},
    'TRX': {'label': 'TRON', 'pattern': _TRON_RE, 'hint': 'T… 34-character base58 address'},
    'SOL': {'label': 'Solana', 'pattern': _SOL_RE, 'hint': '32–44 character base58 address'},
    'TON': {'label': 'TON', 'pattern': _TON_RE, 'hint': 'EQ…/UQ… 48-character address'},
}

GENERIC_MAX_LEN = 255


class AddressValidationError(Exception):
    """Destination address rejected, with a user-safe message."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def validate_address(network_code: str, raw_address: str) -> str:
    """Validate ``raw_address`` for ``network_code``; returns it trimmed.

    Raises :class:`AddressValidationError` with a user-safe message on any
    failure (§76: empty, whitespace, malformed, wrong network, excessive).
    """
    address = (raw_address or '').strip()
    if not address:
        raise AddressValidationError('Destination address is required.')
    if len(address) > GENERIC_MAX_LEN:
        raise AddressValidationError('Destination address is too long.')
    if any(ch.isspace() for ch in address):
        raise AddressValidationError('Destination address cannot contain spaces.')

    rule = NETWORK_RULES.get((network_code or '').upper())
    if rule is None:
        raise AddressValidationError('Selected network is not supported for withdrawals.')
    if rule['pattern'].match(address) is None:
        raise AddressValidationError(
            f'This does not look like a valid {rule["label"]} address (expected {rule["hint"]}). '
            'Double-check the address and the selected network.'
        )
    return address


def address_hint(network_code: str) -> str:
    """Format guidance for the UI (§45)."""
    rule = NETWORK_RULES.get((network_code or '').upper())
    return rule['hint'] if rule else ''
