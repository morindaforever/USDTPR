"""On-chain deposit verification (conversion §4–§5).

SCAFFOLD — disabled by default (``CHAIN_VERIFICATION_ENABLED=False``).

The verification contract below is what a real integration must satisfy per
network before a deposit may be credited. When the gate is enabled, this
module refuses to run until real chain-access infrastructure (node RPC or an
accredited indexer/explorer API with authenticated credentials) is wired in —
it will not approximate or fabricate results. A user-supplied transaction
hash is treated as a lookup KEY, never as proof.

Per-network verification checklist (§4) — each item is verified against the
chain, not the user:

1. the transaction exists on the referenced network
2. it has at least the configured confirmation threshold (CHAIN_CONFIRMATIONS)
3. the destination address equals the platform's assigned deposit address
4. the token contract involved is the official USDT contract (USDT_CONTRACTS)
5. the transferred amount matches (or exceeds) the deposit request
6. the (network, tx_hash) has not already been credited to any account
7. the transaction status is success / not reversed per network rules
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from django.conf import settings

from apps.deposits.models import Deposit
from apps.wallet.models import Network

from .base import NoProviderConfiguredError, TransactionNotVerified, VerificationError, provider_gate

logger = logging.getLogger('integrations.chain')


@dataclass(frozen=True)
class ChainVerificationResult:
    """What a real provider must return for one transaction lookup."""

    network_code: str
    tx_hash: str
    confirmed: bool
    confirmations: int
    to_address: str
    token_contract: str
    amount: str  # exact on-chain amount, decimal string
    status_success: bool


@provider_gate('CHAIN_VERIFICATION_ENABLED')
def verify_deposit_transaction(*, network: Network, tx_hash: str,
                               expected_address: str, expected_amount: str) -> ChainVerificationResult:
    """Verify one deposit against the chain. NOT IMPLEMENTED — real provider required.

    Implementations (per network) must call actual chain infrastructure and
    populate every field of :class:`ChainVerificationResult` from on-chain
    data, then the checks in ``assert_verification_matches`` run here.
    """
    raise NoProviderConfiguredError(
        'CHAIN_VERIFICATION_ENABLED is on, but no chain-access provider is '
        'configured. Wire a node RPC or accredited indexer per network in '
        'apps.integrations.chain before enabling automatic crediting.'
    )


def assert_verification_matches(result: ChainVerificationResult, *, network: Network,
                                expected_address: str, expected_amount: str,
                                confirmation_threshold: int | None = None) -> None:
    """Apply the §4 checklist to a provider result. Raises TransactionNotVerified."""
    required = confirmation_threshold if confirmation_threshold is not None else (
        getattr(settings, 'CHAIN_CONFIRMATIONS', {}).get(network.code)
    )
    contract = getattr(settings, 'USDT_CONTRACTS', {}).get(network.code)
    if contract is None:
        raise TransactionNotVerified(f'Network {network.code} has no configured USDT contract.')
    if not result.status_success:
        raise TransactionNotVerified('On-chain transaction status is not success.')
    if not result.confirmed or result.confirmations < (required or 0):
        raise TransactionNotVerified(
            f'Insufficient confirmations ({result.confirmations} < {required}).'
        )
    if result.to_address.lower() != expected_address.lower():
        raise TransactionNotVerified('Destination address does not match the platform address.')
    if result.token_contract.lower() != contract.lower():
        raise TransactionNotVerified('Token contract is not the official USDT contract for this network.')
    from decimal import Decimal

    if Decimal(result.amount) < Decimal(expected_amount):
        raise TransactionNotVerified('On-chain amount is less than the requested deposit.')


def is_hash_already_credited(*, network_code: str, tx_hash: str) -> bool:
    """§4.6 — the same on-chain transaction may never credit twice.

    Checks APPROVED deposits (historical credits) AND completed payouts'
    hashes are separate domains; here only deposit credits matter.
    """
    return Deposit.objects.filter(
        network__code=network_code, tx_hash__iexact=tx_hash, status=Deposit.Status.APPROVED,
    ).exists()


def verify_deposit(deposit: Deposit) -> ChainVerificationResult:
    """Full pipeline for one pending deposit (lookup + checklist + replay check)."""
    result = verify_deposit_transaction(
        network=deposit.network,
        tx_hash=deposit.tx_hash,
        expected_address=deposit.deposit_address,
        expected_amount=str(deposit.amount),
    )
    if is_hash_already_credited(network_code=deposit.network.code, tx_hash=deposit.tx_hash):
        raise TransactionNotVerified('This transaction hash has already been credited.')
    assert_verification_matches(
        result,
        network=deposit.network,
        expected_address=deposit.deposit_address,
        expected_amount=str(deposit.amount),
    )
    return result


class PayoutError(VerificationError):
    """Raised by payout submission failures."""
