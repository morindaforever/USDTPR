"""Deposit requests.

A Deposit is a user-submitted funding request. Approval/crediting logic
arrives in the deposits section — this module only defines the record and
its invariants (unique IDs, searchable order reference, preserved address).
"""

from django.conf import settings
from django.db import models

from apps.core.db import HumanIDField, TimeStampedModel, money_field


def deposit_screenshot_path(instance, filename: str) -> str:
    """Private-media path for user payment screenshots (§1: optional proof).

    Files live under ``deposit_screenshots/<user pk>/`` inside MEDIA_ROOT
    (never under STATIC). Served only through an authenticated, owner/admin
    view — not by the web server directly.
    """
    import os
    import uuid

    ext = os.path.splitext(filename)[1].lower()[:8] or '.png'
    return f'deposit_screenshots/{instance.user_id}/{uuid.uuid4().hex}{ext}'


class Deposit(TimeStampedModel):
    """User deposit request awaiting review."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    deposit_id = HumanIDField(prefix='DEP', padding=8)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='deposits',
    )
    network = models.ForeignKey(
        'wallet.Network',
        on_delete=models.PROTECT,
        related_name='deposits',
    )
    asset = models.CharField(max_length=10, default='USDT')
    amount = money_field()
    order_id = models.CharField(max_length=64, db_index=True, blank=True)
    tx_hash = models.CharField(max_length=128, blank=True, db_index=True)
    deposit_address = models.CharField(max_length=255, help_text='Address captured at submission time; survives later admin changes.')
    # Optional user-uploaded payment proof. Validation (size/content) is
    # enforced in the service layer; the model only stores the file.
    screenshot = models.FileField(upload_to=deposit_screenshot_path, blank=True, max_length=255)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    admin_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    # The staff account that reviewed (approved/rejected) this deposit.
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deposits_reviewed',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    # Conversion §3–§4: independent on-chain verification. Stamped ONLY by a
    # real provider result (apps.integrations.chain) — never by user input,
    # never fabricated. When chain verification is disabled the field stays
    # empty and admin review is the verification.
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='deposit_amount_positive'),
            # §2: the same on-chain transaction may never be credited twice,
            # regardless of which user/network submitted it. Enforced at the
            # DB level (the service also checks pre-submit for a nice error).
            models.UniqueConstraint(
                fields=['tx_hash'],
                condition=models.Q(status__in=['PENDING', 'APPROVED']) & ~models.Q(tx_hash=''),
                name='deposit_unique_active_tx_hash',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.deposit_id} {self.amount} {self.asset} ({self.status})'
