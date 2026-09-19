"""Payout provider interface for real withdrawals (conversion §8–§9).

SCAFFOLD — disabled by default (``PAYOUTS_ENABLED=False``).

The contract below is what a real custody/payout provider integration must
satisfy. When the gate is enabled without a configured provider this module
raises :class:`NoProviderConfiguredError` — it never fabricates a submission
or a transaction hash. Private keys / provider credentials belong ONLY in
the provider's own secret store (env-injected at runtime, never committed,
never in PostgreSQL, never in frontend code).

Flow contract (§9):

    submit_payout(withdrawal) -> provider payout id (asynchronous)
    poll_payout_status(provider_payout_id) -> pending | confirmed(hash) | failed

A withdrawal may only reach COMPLETED with a REAL hash returned by the
provider after on-chain confirmation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from apps.integrations.base import NoProviderConfiguredError, provider_gate

logger = logging.getLogger('integrations.payouts')


@dataclass(frozen=True)
class PayoutSubmission:
    provider_payout_id: str
    accepted: bool


@dataclass(frozen=True)
class PayoutStatus:
    state: str  # 'pending' | 'confirmed' | 'failed'
    tx_hash: str = ''  # present ONLY when state == 'confirmed' (real hash)


@provider_gate('PAYOUTS_ENABLED')
def submit_payout(*, withdrawal_id: str, network_code: str, to_address: str,
                  amount: str, idempotency_key: str) -> PayoutSubmission:
    """Submit one approved withdrawal to the custody provider. NOT IMPLEMENTED."""
    raise NoProviderConfiguredError(
        'PAYOUTS_ENABLED is on, but no custody/payout provider is configured. '
        'Integrate an authorized provider in apps.integrations.payouts before '
        'enabling automated payouts.'
    )


@provider_gate('PAYOUTS_ENABLED')
def poll_payout_status(*, provider_payout_id: str) -> PayoutStatus:
    """Poll a submitted payout until the provider reports confirmation."""
    raise NoProviderConfiguredError('No payout provider configured.')


# ---------------------------------------------------------------------------
# Webhook handling (§21) — structure provided, verification NOT stubbed out:
# unsigned/failed-verification webhooks are always rejected.
# ---------------------------------------------------------------------------

class WebhookRejected(Exception):
    """Signature, timestamp, or replay check failed."""


def verify_webhook_signature(*, payload_body: bytes, signature_header: str,
                             provider_setting: str) -> None:
    """Verify a provider webhook. NOT IMPLEMENTED — real secret required.

    A real integration must implement constant-time HMAC comparison against
    the provider secret stored OUTSIDE the repository, plus a timestamp /
    replay window check, plus event-id deduplication at the call site.
    """
    secret = None  # read provider secret from secure runtime configuration
    if not secret or not signature_header:
        raise WebhookRejected('Webhook rejected: missing or unverifiable signature.')
    raise NoProviderConfiguredError(
        'No webhook verification implementation for this provider. Wire the '
        "provider's official signature scheme before accepting events."
    )
