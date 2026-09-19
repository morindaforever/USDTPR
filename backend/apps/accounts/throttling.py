"""Endpoint-specific throttle scopes."""

from rest_framework.throttling import ScopedRateThrottle


class AuthLoginThrottle(ScopedRateThrottle):
    scope = 'auth_login'


class AuthPasswordResetThrottle(ScopedRateThrottle):
    scope = 'auth_password_reset'
