"""Production settings.

Selected with DJANGO_SETTINGS_MODULE=config.settings.prod. Hardens on top of
base.py: DEBUG is forced off, secrets are required from the environment, and
HTTPS-only cookie/transport policies are enabled.

Local development must keep using config.settings.dev (the package default).
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403
from .base import REST_FRAMEWORK, env

# ---------------------------------------------------------------------------
# Core hardening — production never boots with the development fallback key.
# ---------------------------------------------------------------------------
DEBUG = False

_SECRET = env('SECRET_KEY', default='')
if not _SECRET or _SECRET == 'dev-only-insecure-key-change-me' or _SECRET.startswith('change-this'):
    raise ImproperlyConfigured(
        'SECRET_KEY must be set to a strong per-environment value in production '
        '(do not use the development fallback).'
    )
SECRET_KEY = _SECRET

_hosts = env('ALLOWED_HOSTS', default=[])
if not _hosts:
    raise ImproperlyConfigured('ALLOWED_HOSTS must be set explicitly in production.')
ALLOWED_HOSTS = _hosts

# ---------------------------------------------------------------------------
# HTTPS / transport security. Enable only behind real TLS — the flags below
# are the standard production posture for a HTTPS deployment.
# ---------------------------------------------------------------------------
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=31536000)  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ---------------------------------------------------------------------------
# Response headers
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'
X_FRAME_OPTIONS = 'DENY'

# ---------------------------------------------------------------------------
# CSRF / CORS — explicit origins only, no wildcard with credentials.
# ---------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])
_cors = env.list('CORS_ALLOWED_ORIGINS', default=[])
if not _cors:
    raise ImproperlyConfigured('CORS_ALLOWED_ORIGINS must list the real frontend origin(s).')
CORS_ALLOWED_ORIGINS = _cors
CORS_ALLOW_CREDENTIALS = env.bool('CORS_ALLOW_CREDENTIALS', default=True)

SESSION_COOKIE_SAMESITE = 'None'
CSRF_COOKIE_SAMESITE = 'None'
# ---------------------------------------------------------------------------
# DRF — anonymous traffic throttled harder in production; keep the dev rates
# for authenticated users (base defaults).
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {**REST_FRAMEWORK}  # copy so base dict is untouched
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    **REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'],
    'anon': '60/min',
}

# 400 pages still render; internal errors never leak tracebacks because
# DEBUG=False. Log everything to stderr; operators attach their own sink.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'plain': {'format': '%(levelname)s %(name)s %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'plain'},
    },
    'root': {'handlers': ['console'], 'level': 'INFO'},
    'loggers': {
        'django.security': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}
