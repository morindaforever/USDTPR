"""KYC / AML / compliance architecture (conversion §17).

SCAFFOLD — disabled by default. Designing the system so a real identity /
sanctions provider can be wired without touching financial code:

    User.kyc_status: unverified -> pending -> approved / rejected
    (never 'approved' without an actual provider-verified process)

Enforcement point: ``ensure_kyc_allowed_for_withdrawal`` — called by the
withdrawal service. With ``KYC_REQUIRED_FOR_WITHDRAWALS=False`` it is a
no-op record-keeper; when the operator enables the flag, only
provider-verified 'approved' users may withdraw. Nothing here ever marks a
user KYC-approved without a real verification event from a configured
provider.

Regulatory note (kept with the code that will enforce it): for an
India-facing VDA service, FIU-IND registration and AML/CFT obligations
apply to covered service providers — obtain professional legal advice and
complete registration BEFORE enabling real customer funds flows.
"""

from __future__ import annotations

import logging

from django.conf import settings

from apps.accounts.models import User

from .base import NoProviderConfiguredError

logger = logging.getLogger('integrations.compliance')


class KYCNotVerified(Exception):
    """The user has not completed a real identity-verification process."""


def start_verification(*, user: User) -> dict:
    """Begin a real KYC session via the configured provider. NOT IMPLEMENTED."""
    if not getattr(settings, 'KYC_REQUIRED_FOR_WITHDRAWALS', False):
        raise NoProviderConfiguredError(
            'KYC flows require a configured identity-verification provider '
            'and are not available.'
        )
    raise NoProviderConfiguredError(
        'No KYC provider configured. Integrate a provider in '
        'apps.integrations.compliance before collecting user documents.'
    )


def ensure_kyc_allowed_for_withdrawal(user: User) -> None:
    """Withdrawal gate (§17). Behavior depends on the operator flag:

    - flag off: no restriction (platform is not yet accepting real
      customer funds flows that mandate KYC).
    - flag on: only ``kyc_status == APPROVED`` — a status that can only be
      set by a real provider verification event — may proceed.
    """
    if not getattr(settings, 'KYC_REQUIRED_FOR_WITHDRAWALS', False):
        return
    if user.kyc_status != User.KYCStatus.APPROVED:
        raise KYCNotVerified(
            'Identity verification is required before withdrawals can be '
            'processed for this account.'
        )
