"""Withdrawal requests and configurable rules.

Withdrawal preserves the destination (address, network, asset, amount) at
request time. WithdrawalRule encodes amount→required-VIP thresholds in the
database so the frontend never hard-codes them.
"""

from django.conf import settings
from django.db import models

from apps.core.db import HumanIDField, TimeStampedModel, money_field


class Withdrawal(TimeStampedModel):
    """User withdrawal request (Section 10).

    Financial terms are SNAPSHOTTED at creation (§16): requested amount,
    fee, and net never change if fee configuration changes later. The
    requested amount is LOCKED via the wallet service at submission and
    finalized/released through it on completion/rejection/failure — this
    model never touches wallet columns.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'
        PROCESSING = 'PROCESSING', 'Processing'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'

    withdrawal_id = HumanIDField(prefix='WDR', padding=8)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='withdrawals',
    )
    network = models.ForeignKey(
        'wallet.Network',
        on_delete=models.PROTECT,
        related_name='withdrawals',
    )
    asset = models.CharField(max_length=10, default='USDT')
    requested_amount = money_field()
    fee_amount = money_field(default=0)
    net_amount = money_field(default=0)
    wallet_address = models.CharField(max_length=255)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    tx_hash = models.CharField(max_length=128, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True, default='')
    admin_note = models.TextField(blank=True)
    # Deterministic per-user creation key (§35, §78): unique per user.
    # Default '' only for pre-Section-10 rows; the service requires a real
    # key for every new withdrawal.
    idempotency_key = models.CharField(max_length=128, default='', blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    processing_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    # The admin who last acted on the request (§23) — never exposed to users.
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='withdrawals_reviewed',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at'], name='withdrawal_user_created_idx'),
            models.Index(fields=['status', '-created_at'], name='withdrawal_status_created_idx'),
            models.Index(fields=['network'], name='withdrawal_network_idx'),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(requested_amount__gt=0), name='withdrawal_amount_positive'),
            models.CheckConstraint(check=models.Q(fee_amount__gte=0), name='withdrawal_fee_nonnegative'),
            models.CheckConstraint(check=models.Q(net_amount__gte=0), name='withdrawal_net_nonnegative'),
            # §35: one withdrawal per (user, idempotency key).
            models.UniqueConstraint(fields=['user', 'idempotency_key'], name='withdrawal_user_idem_unique'),
        ]

    def __str__(self) -> str:
        return f'{self.withdrawal_id} {self.requested_amount} {self.asset} ({self.status})'


class WithdrawalRule(TimeStampedModel):
    """Amount-threshold → required VIP plan rule.

    The backend selects the highest applicable rule for a given amount by
    ordering on ``maximum_amount``; rules are configurable, not hard-coded.
    """

    maximum_amount = money_field(unique=True)
    required_vip_plan = models.ForeignKey(
        'vip.VIPPlan',
        on_delete=models.PROTECT,
        related_name='withdrawal_rules',
        null=True,
        blank=True,
        help_text='Minimum VIP plan required for amounts up to maximum_amount.',
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['maximum_amount']

    def __str__(self) -> str:
        return f'≤ {self.maximum_amount} → {self.required_vip_plan or "none"}'
