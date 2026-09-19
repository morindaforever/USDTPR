"""Shared errors and the primary gate decorator (conversion §4, §18)."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

logger = logging.getLogger('integrations')


class NoProviderConfiguredError(Exception):
    """A real-money gate is enabled but no genuine provider is configured.

    This is a loud, intentional failure: the system must never silently fall
    back to fabricated verification results or invented transaction hashes.
    """


class VerificationError(Exception):
    """An on-chain verification attempt failed for a technical reason."""


class TransactionNotVerified(Exception):
    """The on-chain evidence does not match the submitted deposit."""


def provider_gate(setting_name: str) -> Callable:
    """Guard an integration entrypoint behind its settings gate.

    When the gate is disabled the decorated function raises immediately with
    a clear error — callers translate this into honest operator-facing
    messages. When enabled but unconfigured, ``NoProviderConfiguredError``
    fires from the function body.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not getattr(settings, setting_name, False):
                raise NoProviderConfiguredError(
                    f'{setting_name} is disabled — this operation requires a '
                    f'configured, authorized provider and is not available.'
                )
            return func(*args, **kwargs)

        return wrapper

    return decorator


def provider_unavailable_response(exc: NoProviderConfiguredError) -> Response:
    """Uniform DRF response for disabled-integration endpoints (§18)."""
    return Response(
        {
            'success': False,
            'message': str(exc),
            'errors': {},
            'code': 'provider_disabled',
        },
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )
