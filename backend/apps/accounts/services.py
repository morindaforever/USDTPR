"""Authentication domain services.

All business rules for auth live here (not in views/serializers) so they
can be reused by management commands, Celery tasks, or admin actions.
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import timedelta

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import EmailValidator, RegexValidator
from django.db import transaction
from django.utils import timezone

from apps.notifications.services import notify
from .models import LoginActivity, PasswordResetToken, User

EMAIL_RE = EmailValidator()
PHONE_RE = RegexValidator(regex=r'^\+?[0-9]{7,15}$')
# Referral codes use an unambiguous alphabet (no 0/O/1/I/L).
REFERRAL_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'


class AuthError(Exception):
    """Domain-level auth error with a user-safe message and field errors."""

    def __init__(self, message: str, errors: dict | None = None, http_status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}
        self.http_status = http_status


# --------------------------------------------------------------------------- #
# Identifier resolution (login with email / phone / user ID)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Identifier:
    kind: str   # 'email' | 'phone' | 'user_id'
    value: str


def resolve_identifier(raw: str) -> Identifier | None:
    """Classify a login identifier and normalize it."""
    value = (raw or '').strip()
    if not value:
        return None
    try:
        EMAIL_RE(value)
        return Identifier('email', value.lower())
    except DjangoValidationError:
        pass
    candidate = value if value.startswith('+') else f'+{value}'
    try:
        PHONE_RE(candidate)
        return Identifier('phone', candidate)
    except DjangoValidationError:
        pass
    if User.objects.filter(user_id__iexact=value.upper()).exists():
        return Identifier('user_id', value.upper())
    return None


def find_user_by_identifier(identifier: Identifier) -> User | None:
    if identifier.kind == 'email':
        return User.objects.filter(email__iexact=identifier.value).first()
    if identifier.kind == 'phone':
        return (
            User.objects.filter(phone=identifier.value).first()
            or User.objects.filter(phone=identifier.value.lstrip('+')).first()
        )
    return User.objects.filter(user_id__iexact=identifier.value).first()


# --------------------------------------------------------------------------- #
# Brute-force protection (cache-based, per identifier and per IP)
# --------------------------------------------------------------------------- #
FAILED_LOGIN_WINDOW = 900          # 15 minutes
FAILED_LOGIN_LIMIT = 5             # attempts per window
MAX_CLIENTS_PER_IP = 20            # distinct identifiers per IP per window
RESET_TOKEN_TTL = 60 * 60          # 1 hour


def _cache_key(kind: str, *parts: str) -> str:
    import hashlib

    digest = hashlib.sha256('|'.join(parts).encode()).hexdigest()[:32]
    return f'auth:{kind}:{digest}'


def _get_cache():
    from django.core.cache import cache

    return cache


def check_login_allowed(identifier_value: str, ip: str | None) -> None:
    """Raise AuthError when too many recent failures are recorded."""
    cache = _get_cache()
    id_key = _cache_key('fail_id', identifier_value.lower())
    if cache.get(id_key, 0) >= FAILED_LOGIN_LIMIT:
        raise AuthError('Too many attempts. Please try again later.', http_status=429)
    if ip and cache.get(_cache_key('fail_ip', ip), 0) >= MAX_CLIENTS_PER_IP:
        raise AuthError('Too many attempts. Please try again later.', http_status=429)


def record_failed_login(identifier_value: str, ip: str | None) -> None:
    cache = _get_cache()
    id_key = _cache_key('fail_id', identifier_value.lower())
    ip_key = _cache_key('fail_ip', ip or 'unknown')
    try:
        cache.incr(id_key)
    except ValueError:
        cache.set(id_key, 1, FAILED_LOGIN_WINDOW)
    try:
        cache.incr(ip_key)
    except ValueError:
        cache.set(ip_key, 1, FAILED_LOGIN_WINDOW)
    cache.touch(id_key, FAILED_LOGIN_WINDOW)
    cache.touch(ip_key, FAILED_LOGIN_WINDOW)


def clear_failed_logins(identifier_value: str, ip: str | None) -> None:
    cache = _get_cache()
    cache.delete(_cache_key('fail_id', identifier_value.lower()))
    if ip:
        cache.delete(_cache_key('fail_ip', ip))


def client_ip(request) -> str | None:
    """Extract client IP, honoring the Vite dev proxy."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def client_user_agent(request) -> str:
    return (request.META.get('HTTP_USER_AGENT') or '')[:512]


def ensure_active(user) -> None:
    """Raise AuthError unless the account may use protected functionality.

    Server-side account-status enforcement (Section 14 §9): suspended and
    banned users must not deposit, purchase, withdraw, or message support —
    hiding UI buttons is never the security boundary. BANNED wording stays
    generic to avoid confirming account existence to a potential attacker.
    """
    from .models import User

    if user.account_status == User.AccountStatus.BANNED:
        raise AuthError('This account can no longer be used.')
    if user.account_status == User.AccountStatus.SUSPENDED:
        raise AuthError('This account is suspended. Contact support.')


def record_login_activity(
    user: User,
    outcome: LoginActivity.Outcome,
    request=None,
    identifier_used: str = '',
    detail: str = '',
) -> None:
    LoginActivity.objects.create(
        user=user,
        outcome=outcome,
        identifier_used=identifier_used[:255],
        ip_address=client_ip(request) if request else None,
        user_agent=client_user_agent(request) if request else '',
        detail=detail[:255],
    )


# --------------------------------------------------------------------------- #
# Credentials checking with account status enforcement
# --------------------------------------------------------------------------- #
def authenticate_user(identifier: Identifier, password: str) -> tuple[User | None, str | None]:
    """Return (user, error_message). Enforces account status.

    Error messages are deliberately generic to prevent enumeration.
    """
    user = find_user_by_identifier(identifier)
    if user is None:
        # Burn comparable time to the password check to blunt timing probes.
        authenticate(username='nonexistent@example.com', password=password)
        return None, 'Invalid credentials.'
    if user.account_status == User.AccountStatus.BANNED:
        return None, 'Invalid credentials.'
    if user.account_status == User.AccountStatus.SUSPENDED:
        return None, 'This account is suspended. Contact support.'
    if not user.check_password(password):
        return None, 'Invalid credentials.'
    return user, None


# --------------------------------------------------------------------------- #
# Registration
# --------------------------------------------------------------------------- #
@dataclass
class RegistrationResult:
    user: User
    referral_created: bool = False
    referrer: User | None = None
    warnings: list[str] = field(default_factory=list)


def validate_registration(
    *,
    full_name: str,
    email: str,
    phone: str,
    password: str,
    password_confirm: str,
    referral_code: str = '',
) -> dict:
    """Mirror all frontend validation rules; returns normalized data.

    Raises AuthError with per-field errors suitable for the API envelope.
    """
    errors: dict[str, list[str]] = {}

    full_name = (full_name or '').strip()
    email = (email or '').strip().lower()
    phone = (phone or '').strip()
    referral_code = (referral_code or '').strip().upper()

    if not full_name:
        errors.setdefault('full_name', []).append('Full name cannot be empty.')
    if not email:
        errors.setdefault('email', []).append('Email is required.')
    else:
        try:
            EMAIL_RE(email)
        except DjangoValidationError:
            errors.setdefault('email', []).append('Enter a valid email address.')
    if not phone:
        errors.setdefault('phone', []).append('Phone number is required.')
    else:
        try:
            PHONE_RE(phone)
        except DjangoValidationError:
            errors.setdefault('phone', []).append('Enter a valid phone number.')

    if not password:
        errors.setdefault('password', []).append('Password is required.')
    else:
        try:
            validate_password(password)
        except DjangoValidationError as exc:
            errors.setdefault('password', []).extend(exc.messages)
    if password != password_confirm:
        errors.setdefault('password_confirm', []).append('Passwords do not match.')

    if errors:
        raise AuthError('Please correct the highlighted fields.', errors)

    if User.objects.filter(email__iexact=email).exists():
        raise AuthError(
            'Please correct the highlighted fields.',
            {'email': ['An account with this email already exists.']},
        )
    normalized_phone = phone if phone.startswith('+') else f'+{phone}'
    if User.objects.filter(phone__in=[phone, normalized_phone]).exists():
        raise AuthError(
            'Please correct the highlighted fields.',
            {'phone': ['An account with this phone number already exists.']},
        )

    referrer = None
    if referral_code:
        referrer = User.objects.filter(referral_code=referral_code).first()
        if referrer is None:
            raise AuthError(
                'Please correct the highlighted fields.',
                {'referral_code': ['Invalid referral code.']},
            )
        # Section 9 §6: the referrer must hold an active account — suspended
        # and banned users cannot pick up new team members.
        if referrer.account_status != User.AccountStatus.ACTIVE:
            raise AuthError(
                'Please correct the highlighted fields.',
                {'referral_code': ['This referral code is not available.']},
            )

    return {
        'full_name': full_name,
        'email': email,
        'phone': normalized_phone,
        'password': password,
        'referrer': referrer,
    }


def generate_referral_code() -> str:
    """7-char URL-safe code from an unambiguous alphabet."""
    for _ in range(20):
        code = ''.join(secrets.choice(REFERRAL_ALPHABET) for _ in range(7))
        if not User.objects.filter(referral_code=code).exists():
            return code
    raise RuntimeError('Could not generate a unique referral code')


@transaction.atomic
def register_user(
    *,
    full_name: str,
    email: str,
    phone: str,
    password: str,
    referral_code: str = '',
) -> RegistrationResult:
    """Create the user + wallet (+ optional referral row) atomically.

    The DB constraints from Section 2 back every invariant asserted here.
    """
    data = validate_registration(
        full_name=full_name,
        email=email,
        phone=phone,
        password=password,
        password_confirm=password,
        referral_code=referral_code,
    )

    user = User(
        full_name=data['full_name'],
        email=data['email'],
        phone=data['phone'],
        referred_by=data['referrer'],
    )
    user.set_password(data['password'])
    user.referral_code = generate_referral_code()
    user.full_clean(exclude={'password', 'user_id'})
    user.save()

    from apps.wallet.models import Wallet

    Wallet.objects.create(user=user)  # all buckets default to zero

    referral_created = False
    if data['referrer'] is not None:
        # Section 9: create through the referrals service so eligibility,
        # one-referrer, and cycle invariants are enforced in one place
        # (§43/§44 audit + notification happen inside the service).
        from apps.referrals.services import create_relationship

        result = create_relationship(referrer=data['referrer'], referred_user=user)
        referral_created = result.created

    return RegistrationResult(user=user, referral_created=referral_created, referrer=data['referrer'])


# --------------------------------------------------------------------------- #
# Password reset tokens
# --------------------------------------------------------------------------- #
def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_password_reset(user: User, ip: str | None = None) -> str:
    """Create a single-use reset token; returns the raw token once."""
    raw = secrets.token_urlsafe(32)
    PasswordResetToken.objects.create(
        user=user,
        token_hash=_hash_token(raw),
        expires_at=timezone.now() + timedelta(seconds=RESET_TOKEN_TTL),
        created_ip=ip,
    )
    return raw


def validate_password_reset(raw_token: str) -> PasswordResetToken:
    """Return a valid, unused, unexpired token row or raise AuthError."""
    row = PasswordResetToken.objects.filter(token_hash=_hash_token(raw_token or '')).first()
    if row is None or row.is_used() or row.is_expired():
        raise AuthError('This password reset link is invalid or has expired.')
    return row


def consume_password_reset(raw_token: str, new_password: str) -> User:
    """Validate token, set the new password, invalidate the token."""
    row = validate_password_reset(raw_token)
    try:
        validate_password(new_password, user=row.user)
    except DjangoValidationError as exc:
        raise AuthError('Please correct the highlighted fields.', {'password': list(exc.messages)}) from exc
    row.user.set_password(new_password)
    row.user.save(update_fields=['password'])
    row.used_at = timezone.now()
    row.save(update_fields=['used_at'])
    return row.user


def change_password(user: User, current_password: str, new_password: str) -> None:
    """Authenticated password change; requires the current password."""
    if not user.check_password(current_password):
        raise AuthError(
            'Please correct the highlighted fields.',
            {'current_password': ['Current password is incorrect.']},
        )
    try:
        validate_password(new_password, user=user)
    except DjangoValidationError as exc:
        raise AuthError('Please correct the highlighted fields.', {'password': list(exc.messages)}) from exc
    if current_password == new_password:
        raise AuthError(
            'Please correct the highlighted fields.',
            {'password': ['New password must be different from the current password.']},
        )
    user.set_password(new_password)
    user.save(update_fields=['password'])
    # §15: security notification (user-initiated, so not event-keyed —
    # every real change should notify; no retry can replay it).
    notify(
        user=user,
        notification_type='SECURITY',
        title='Password Changed',
        message='Your account password was successfully changed.',
    )
