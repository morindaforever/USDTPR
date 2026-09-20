"""VIP plans, purchases, and rewards.

Purchases snapshot plan terms (name, amounts, rate) so later admin edits to
a plan never rewrite history for existing purchases. Rewards are protected
against duplicate crediting per (purchase, date) — Celery retries cannot
double-pay.
"""

from django.conf import settings
from django.db import models

from apps.core.db import HumanIDField, TimeStampedModel, money_field


class VIPPlan(TimeStampedModel):
    """Configurable VIP plan definition."""

    name = models.CharField(max_length=64, unique=True)
    plan_number = models.PositiveIntegerField(unique=True)
    investment_amount = money_field()
    target_amount = money_field()
    daily_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        help_text='Fraction of investment credited per day, e.g. 0.25 = 25%.',
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'plan_number']
        constraints = [
            models.CheckConstraint(check=models.Q(target_amount__gt=0), name='vipplan_target_positive'),
            models.CheckConstraint(check=models.Q(daily_rate__gt=0), name='vipplan_rate_positive'),
        ]

    @property
    def is_welcome_plan(self) -> bool:
        """Zero-investment promotional plan (identified by name, not a flag
        column — no new fields/migrations)."""
        return self.name.upper().startswith('WELCOME')

    def __str__(self) -> str:
        return f'{self.name} (#{self.plan_number})'


class VIPPurchase(TimeStampedModel):
    """A user's purchase of a VIP plan, with immutable term snapshots."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACTIVE = 'ACTIVE', 'Active'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    purchase_id = HumanIDField(prefix='VIP', padding=8)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='vip_purchases',
    )
    vip_plan = models.ForeignKey(VIPPlan, on_delete=models.PROTECT, related_name='purchases')
    # Snapshots — do NOT follow later plan edits.
    plan_name_snapshot = models.CharField(max_length=64)
    investment_amount = money_field()
    target_amount = money_field()
    daily_rate_snapshot = models.DecimalField(max_digits=5, decimal_places=4)
    amount_received = money_field(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Client/backend idempotency reference for the purchase request; the
    # wallet-service debit uses the derived key 'VIP_PURCHASE_<this value>'
    # so a retried request can never debit twice or create two purchases.
    idempotency_key = models.CharField(max_length=128, null=True, blank=True, db_index=True)
    # Last reward cycle fully consumed (target reached mid-cycle). When set,
    # that cycle must never pay again — the UNIQUE(purchase, reward_date)
    # constraint alone cannot express this because no VIPReward row exists
    # for a zero-remaining cycle.
    last_reward_cycle = models.DateField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status', '-created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(idempotency_key__startswith='WELCOME_CLAIM_'),
                name='vippurchase_one_welcome_claim_per_user',
            ),
        ]

    def save(self, *args, **kwargs):
        # First save copies the plan terms into the row.
        if not self.plan_name_snapshot and self.vip_plan_id:
            plan = self.vip_plan
            self.plan_name_snapshot = plan.name
            self.investment_amount = plan.investment_amount
            self.target_amount = plan.target_amount
            self.daily_rate_snapshot = plan.daily_rate
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f'{self.purchase_id} {self.plan_name_snapshot} ({self.status})'


class VIPReward(TimeStampedModel):
    """One day's reward accrual for an active purchase."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        FAILED = 'FAILED', 'Failed'
        REVERSED = 'REVERSED', 'Reversed'

    reward_id = HumanIDField(prefix='REW', padding=8)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='vip_rewards',
    )
    vip_purchase = models.ForeignKey(
        VIPPurchase,
        on_delete=models.PROTECT,
        related_name='rewards',
    )
    reward_date = models.DateField(db_index=True)
    calculated_amount = money_field()
    credited_amount = money_field(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    wallet_transaction = models.ForeignKey(
        'wallet.WalletTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vip_rewards',
    )
    # Set when the row leaves PENDING (credited, or failed and recorded).
    processed_at = models.DateTimeField(null=True, blank=True)
    # Short internal failure note (e.g. 'wallet-credit-failed'). User-facing
    # views never render this; it exists for troubleshooting only.
    error_info = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reward_date', '-created_at']
        indexes = [
            models.Index(fields=['user', '-reward_date'], name='vipreward_user_date_idx'),
            models.Index(fields=['vip_purchase', 'status'], name='vipreward_purchase_status_idx'),
            models.Index(fields=['reward_date', 'status'], name='vipreward_date_status_idx'),
        ]
        constraints = [
            # ONE reward row per purchase per cycle — Celery retries, double
            # beat ticks, and racing workers cannot create a second row.
            models.UniqueConstraint(
                fields=['vip_purchase', 'reward_date'],
                name='vipreward_unique_purchase_date',
            ),
            # A credited amount is always non-negative and never exceeds the
            # calculated amount (target caps shrink credited, never inflate).
            models.CheckConstraint(check=models.Q(credited_amount__gte=0), name='vipreward_credited_nonnegative'),
            models.CheckConstraint(
                check=models.Q(credited_amount__lte=models.F('calculated_amount')),
                name='vipreward_credited_lte_calculated',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.reward_id} {self.reward_date} {self.status}'
