"""
Base Django settings for the USDT platform.

Environment-specific overrides live in `dev.py` / `prod.py` and are selected
via the DJANGO_SETTINGS_MODULE environment variable. All secrets and
connection details come from environment variables (see backend/.env.example).
"""

from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

# backend/ directory
BASE_DIR = Path(__file__).resolve().parents[2]

# Read backend/.env when present. In production, real environment variables
# take precedence; the .env file is a development convenience.
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1']),
)
environ.Env.read_env(BASE_DIR / '.env')

# --------------------------------------------------------------------------- #
# Core
# --------------------------------------------------------------------------- #
SECRET_KEY = env('SECRET_KEY', default='dev-only-insecure-key-change-me')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Custom user model (apps.accounts.User) — required before first migrate.
AUTH_USER_MODEL = 'accounts.User'

# Production safety (§18): True only during automated test runs. Probed via
# sys.argv in test context because the test runner copies settings; dev
# utilities (e.g. seed_demo_data) check TESTING | DEBUG.
TESTING = (
    'test' in __import__('sys').argv
    or any(arg.endswith('manage.py') is False and 'test' == arg.split('/')[-1] for arg in __import__('sys').argv)
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    # Local apps — business logic arrives section by section.
    'apps.core',
    'apps.accounts',
    'apps.wallet',
    'apps.deposits',
    'apps.withdrawals',
    'apps.vip',
    'apps.referrals',
    'apps.support',
    'apps.notifications',
    'apps.adminpanel',
    'apps.integrations',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# --------------------------------------------------------------------------- #
# Database — PostgreSQL via DATABASE_URL
# --------------------------------------------------------------------------- #
DATABASES = {
    'default': env.db_url(
        'DATABASE_URL',
        default='postgres://usdt_platform:usdt_platform@localhost:5432/usdt_platform',
    ),
}
DATABASES['default']['ENGINE'] = 'django.db.backends.postgresql'
# Default connection auto-creation for the whole platform; financial apps
# must open their own transactions explicitly (Section 2+ rule).
DATABASES['default']['ATOMIC_REQUESTS'] = False
DATABASES['default']['CONN_MAX_AGE'] = 60

# --------------------------------------------------------------------------- #
# REST framework
# --------------------------------------------------------------------------- #
REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # Auth permissions are tightened per-endpoint by later sections; the
    # default stays permissive only while placeholder endpoints exist.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/min',
        'user': '1000/min',
        # Tight throttle backing the login endpoint (defense in depth with
        # the identifier+IP counter in accounts.services).
        'auth_login': '10/min',
        'auth_password_reset': '5/min',
        # Financial submissions (deposit/withdrawal/VIP purchase) — generous
        # enough for legitimate use, tight enough to blunt spam/replay floods
        # (Section 14 §30). Support messaging keeps its per-user counters in
        # apps.support.services.
        'fin_write': '30/min',
    },
    'EXCEPTION_HANDLER': 'apps.core.exceptions.api_exception_handler',
}

# --------------------------------------------------------------------------- #
# JWT (SimpleJWT)
# --------------------------------------------------------------------------- #
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# Password reset tokens expire after 1 hour.
PASSWORD_RESET_TIMEOUT = 60 * 60

# --------------------------------------------------------------------------- #
# Password policy (Django validators — no custom crypto)
# --------------------------------------------------------------------------- #
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# --------------------------------------------------------------------------- #
# CORS — frontend dev server
# --------------------------------------------------------------------------- #
CORS_ALLOWED_ORIGINS = env.list(
    'CORS_ALLOWED_ORIGINS',
    default=['http://localhost:5173', 'http://127.0.0.1:5173'],
)

# --------------------------------------------------------------------------- #
# Redis + Celery
# --------------------------------------------------------------------------- #
REDIS_URL = env('REDIS_URL', default='redis://localhost:6379/0')

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Scheduled jobs (Section 8). Defined here — not in app code — because
# config/celery.py loads before Django's app registry. Celery resolves the
# crontab against CELERY_TIMEZONE (the project timezone), so no hard-coded
# UTC assumption in task code. Duplicate ticks / retries are harmless: the
# reward engine is idempotent per (purchase, cycle).
CELERY_BEAT_SCHEDULE = {
    'process-daily-vip-rewards': {
        'task': 'vip.process_daily_vip_rewards',
        # 00:15 local time, just after the calendar-day cycle rolls over.
        'schedule': crontab(hour=0, minute=15),
        'options': {'expires': 3600},
    },
}

# --------------------------------------------------------------------------- #
# Production integrations (conversion §3–§5, §8, §12, §17, §21).
#
# Every integration that touches real money or external infrastructure is
# DISABLED by default. The platform runs in admin-reviewed manual mode until
# a real provider is configured. Enabling a gate without the corresponding
# provider configuration raises NoProviderConfiguredError at call time —
# the system never falls back to fabricated data.
# --------------------------------------------------------------------------- #
# Independent on-chain verification of submitted deposit transactions.
CHAIN_VERIFICATION_ENABLED = env.bool('CHAIN_VERIFICATION_ENABLED', default=False)
# Automated payout-provider submission for withdrawals (§9). When disabled,
# withdrawals are settled manually by operations and completed only with a
# REAL on-chain transaction hash provided by the operator.
PAYOUTS_ENABLED = env.bool('PAYOUTS_ENABLED', default=False)
# §12: the VIP reward model must not run for public users until the reward
# scheme has been legally reviewed and authorized. Celery automation stays
# off; staff may still run the audited manual command.
REWARD_PAYOUTS_ENABLED = env.bool('REWARD_PAYOUTS_ENABLED', default=False)
# §17: require completed identity verification before withdrawals.
KYC_REQUIRED_FOR_WITHDRAWALS = env.bool('KYC_REQUIRED_FOR_WITHDRAWALS', default=False)

# §5 — official USDT token contracts per Network.code. Verification checks
# the ACTUAL token contract involved in a transaction; a symbol is never
# proof. Networks without an entry here cannot be auto-verified.
USDT_CONTRACTS = {
    'TRX': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',          # TRC-20 (TRON)
    'BSC': '0x55d398326f99059fF775485246999027B3197955',  # BEP-20
    'ETH': '0xdAC17F958D2ee523a2206206994597C13D831ec7',  # ERC-20
    'POL': '0xc2132D05D31c914a87C6611C10748AEb04B58e8F',  # Polygon PoS
}
# Confirmed-block thresholds per network before a deposit may be credited.
CHAIN_CONFIRMATIONS = {'TRX': 19, 'BSC': 15, 'ETH': 12, 'POL': 30}

# --------------------------------------------------------------------------- #
# i18n / tz
# --------------------------------------------------------------------------- #
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# --------------------------------------------------------------------------- #
# Security: CSRF & cookies
# --------------------------------------------------------------------------- #
# Cookie-based auth endpoints (logout, refresh, password reset) sent from
# the Vite dev origin must carry the CSRF cookie value.
CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]
CSRF_COOKIE_HTTPONLY = False  # frontend must read it to set X-CSRFToken

# Refresh-cookie policy. 'Lax' keeps the cookie on same-site API calls (the
# common app.example.com + api.example.com setup is still same-site for a
# parent domain). Only flip to 'None' when the API is served from a wholly
# different registrable domain than the frontend (requires HTTPS).
REFRESH_COOKIE_SAMESITE = env('REFRESH_COOKIE_SAMESITE', default='Lax')
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

# --------------------------------------------------------------------------- #
# Cache (rate limiting, throttles) — Redis-backed, shared across workers
# --------------------------------------------------------------------------- #
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': env('REDIS_URL', default='redis://localhost:6379/0'),
    },
}

# --------------------------------------------------------------------------- #
# Static / media
# --------------------------------------------------------------------------- #
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# User uploads (deposit screenshots, withdrawal QR images) live in private
# media, served ONLY through authenticated views — never by the web server.
# Override the cap per environment if needed (bytes).
MAX_UPLOAD_BYTES = env.int('MAX_UPLOAD_BYTES', default=5 * 1024 * 1024)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Public URL of the frontend — used to build shareable referral links
# (Section 9 §4). Never hard-code a production domain; set per environment.
# FRONTEND_URL is accepted as an alias. Unset + DEBUG → localhost (Vite dev
# default); unset in production → relative links, so a localhost/wrong
# domain can never leak into user-facing URLs.
PUBLIC_APP_URL = env('PUBLIC_APP_URL', default='') or env('FRONTEND_URL', default='')
