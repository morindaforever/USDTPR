"""Accounts models: the custom User plus authentication support tables.

- User: platform identity (business ID, referral identity, status).
- LoginActivity: security-monitoring log of login/logout attempts.
- PasswordResetToken: hashed, single-use, time-limited reset tokens.
"""

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
from django.db import models

from apps.core.db import HumanIDField


class UserManager(BaseUserManager):
    """Manager where email is the username field."""

    use_in_migrations = True

    def _create_user(self, email, password, phone=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email).lower()
        user = self.model(email=email, phone=phone, **extra_fields)
        user.set_password(password)  # hashed, never plaintext
        user.referral_code = user._generate_referral_code()
        # user_id is assigned by the DB layer on insert; excluded here.
        user.full_clean(exclude={'password', 'user_id'})
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, phone=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, phone, **extra_fields)

    def create_superuser(self, email, password=None, phone=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('account_status', self.model.AccountStatus.ACTIVE)
        if extra_fields['is_staff'] is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields['is_superuser'] is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self._create_user(email, password, phone, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Platform user. Deletion is disabled in practice — suspend instead."""

    class AccountStatus(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        SUSPENDED = 'SUSPENDED', 'Suspended'
        BANNED = 'BANNED', 'Banned'

    user_id = HumanIDField(prefix='USR', padding=6)
    full_name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(unique=True)
    phone = models.CharField(
        max_length=20,
        unique=True,
        validators=[RegexValidator(regex=r'^\+?[0-9]{7,15}$')],
    )
    referral_code = models.CharField(max_length=12, unique=True, editable=False)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='direct_referrals',
    )
    account_status = models.CharField(
        max_length=12,
        choices=AccountStatus.choices,
        default=AccountStatus.ACTIVE,
    )

    class KYCStatus(models.TextChoices):
        # 'APPROVED' can ONLY be set by a real provider verification event
        # (conversion §17) — never by an API request or a fixture shortcut.
        UNVERIFIED = 'UNVERIFIED', 'Unverified'
        PENDING = 'PENDING', 'Verification pending'
        APPROVED = 'APPROVED', 'Verified'
        REJECTED = 'REJECTED', 'Verification failed'

    kyc_status = models.CharField(
        max_length=12,
        choices=KYCStatus.choices,
        default=KYCStatus.UNVERIFIED,
        db_index=True,
        help_text='Set ONLY by a real identity-verification provider event.',
    )
    kyc_verified_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone']

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['account_status']),
        ]

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = self._generate_referral_code()
        super().save(*args, **kwargs)

    def _generate_referral_code(self) -> str:
        """Short URL-safe code; uniqueness enforced by the DB + retry loop."""
        import secrets

        alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'  # no ambiguous chars
        for _ in range(10):
            code = ''.join(secrets.choice(alphabet) for _ in range(7))
            if not User.objects.filter(referral_code=code).exists():
                return code
        raise RuntimeError('Could not generate a unique referral code')

    def clean(self):
        if self.referred_by_id and self.referred_by_id == self.pk:
            raise ValueError('A user cannot refer themselves.')

    def __str__(self) -> str:
        return f'{self.user_id or "USR-unassigned"} ({self.email})'


class LoginActivity(models.Model):
    """One row per login/logout attempt for security monitoring."""

    class Outcome(models.TextChoices):
        SUCCESS = 'SUCCESS', 'Success'
        FAILED = 'FAILED', 'Failed'
        LOGOUT = 'LOGOUT', 'Logout'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='login_activities',
    )
    identifier_used = models.CharField(max_length=255, blank=True)
    outcome = models.CharField(max_length=8, choices=Outcome.choices, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    detail = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['outcome', '-created_at']),
        ]

    def __str__(self) -> str:
        return f'{self.user} {self.outcome} at {self.created_at:%Y-%m-%d %H:%M}'


class PasswordResetToken(models.Model):
    """Single-use, time-limited, unpredictable password reset tokens.

    Only the hash of the token is stored; the raw token is shown/emailed to
    the user exactly once. Expiry and single-use semantics are enforced in
    the service layer, with the DB providing the lookup.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def is_expired(self) -> bool:
        from django.utils import timezone

        return timezone.now() >= self.expires_at

    def is_used(self) -> bool:
        return self.used_at is not None

    def __str__(self) -> str:
        return f'Reset token for {self.user} (expires {self.expires_at:%Y-%m-%d %H:%M})'
