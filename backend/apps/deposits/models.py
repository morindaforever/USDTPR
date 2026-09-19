"""Deposit requests.

A Deposit is a user-submitted funding request. Approval/crediting logic
arrives in the deposits section — this module only defines the record and
its invariants (unique IDs, searchable order reference, preserved address).
"""

from django.conf import settings
from django.db import models

from apps.core.db import HumanIDField, TimeStampedModel, money_field


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
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True)
    admin_note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
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
        ]

    def __str__(self) -> str:
        return f'{self.deposit_id} {self.amount} {self.asset} ({self.status})'
