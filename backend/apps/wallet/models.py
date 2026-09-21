"""Wallet, ledger, networks, and deposit addresses.

Financial invariants encoded here:
- Wallet holds named balance buckets, all Decimal(24,8), defaulting to zero.
- Every balance movement must be recorded as a WalletTransaction row
  describing what moved, where, and why (the audit trail for money).
- ``idempotency_key`` makes retries of deposits/rewards/payouts safe:
  the same key can only ever produce one ledger row.

ACCOUNTING POLICY (authoritative — see docs/WALLET.md for the full version):
- ``total_balance`` is a DERIVED display aggregate maintained by the wallet
  service: total = deposit + withdrawable + bonus + locked + pending. It is
  never an independent store of value and credits/debits never target it
  directly. (It is deliberately NOT assumed to equal deposit + withdrawable
  — bonus, locked, and pending also count toward holdings.)
- Category buckets (deposit/withdrawable/bonus) mark WHERE funds came from
  and what they may be used for; locked/pending mark in-flight states.
- The ledger (WalletTransaction) is the source of truth. Only COMPLETED
  rows affect balances; PENDING rows are records of intent, REVERSED/FAILED
  rows are historical. Movement between buckets produces one ledger row per
  affected bucket (e.g. lock = DEBIT withdrawable + CREDIT locked).
- Every mutation goes through apps.wallet.services — never write wallet
  columns directly.
"""

from django.conf import settings
from django.db import models

from apps.core.db import (
    HumanIDField,
    TimeStampedModel,
    money_field,
    optional_money_field,
)


class Wallet(TimeStampedModel):
    """Per-user balance container (1:1 with User).

    Buckets are plain Decimal columns; the ledger (WalletTransaction) is the
    source of truth for how they got there. Constraints prevent negative
    balances — reconciliation uses explicit ADJUSTMENT ledger entries rather
    than silently allowing negative money.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wallet',
    )
    total_balance = money_field(default=0)
    deposit_balance = money_field(default=0)
    withdrawable_balance = money_field(default=0)
    pending_balance = money_field(default=0)
    locked_balance = money_field(default=0)
    bonus_balance = money_field(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(total_balance__gte=0), name='wallet_total_nonnegative'),
            models.CheckConstraint(check=models.Q(deposit_balance__gte=0), name='wallet_deposit_nonnegative'),
            models.CheckConstraint(check=models.Q(withdrawable_balance__gte=0), name='wallet_withdrawable_nonnegative'),
            models.CheckConstraint(check=models.Q(pending_balance__gte=0), name='wallet_pending_nonnegative'),
            models.CheckConstraint(check=models.Q(locked_balance__gte=0), name='wallet_locked_nonnegative'),
            models.CheckConstraint(check=models.Q(bonus_balance__gte=0), name='wallet_bonus_nonnegative'),
        ]

    def __str__(self) -> str:
        return f'Wallet for {self.user}'


class WalletTransaction(TimeStampedModel):
    """Central financial ledger. Append-only; never update amounts in place.

    A reversal is expressed as a new opposite-direction transaction
    referencing the original via ``reference_type``/``reference_id``.
    """

    class TransactionType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
        VIP_PURCHASE = 'VIP_PURCHASE', 'VIP purchase'
        VIP_REWARD = 'VIP_REWARD', 'VIP reward'
        REFERRAL_COMMISSION = 'REFERRAL_COMMISSION', 'Referral commission'
        REFERRAL_REWARD = 'REFERRAL_REWARD', 'Referral reward'
        WELCOME_BONUS = 'WELCOME_BONUS', 'Welcome bonus'
        REFUND = 'REFUND', 'Refund'
        ADJUSTMENT = 'ADJUSTMENT', 'Adjustment'
        # Internal balance-movement categories used by the wallet service.
        LOCK = 'LOCK', 'Lock (withdrawable → locked)'
        RELEASE = 'RELEASE', 'Release (locked → withdrawable)'
        TRANSFER = 'TRANSFER', 'Internal bucket transfer'

    class Direction(models.TextChoices):
        CREDIT = 'CREDIT', 'Credit'
        DEBIT = 'DEBIT', 'Debit'

    class BalanceType(models.TextChoices):
        TOTAL = 'TOTAL', 'Total'
        DEPOSIT = 'DEPOSIT', 'Deposit'
        WITHDRAWABLE = 'WITHDRAWABLE', 'Withdrawable'
        BONUS = 'BONUS', 'Bonus'
        LOCKED = 'LOCKED', 'Locked'
        PENDING = 'PENDING', 'Pending'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        COMPLETED = 'COMPLETED', 'Completed'
        REVERSED = 'REVERSED', 'Reversed'
        FAILED = 'FAILED', 'Failed'

    transaction_id = HumanIDField(prefix='TXN', padding=8)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='wallet_transactions',
    )
    transaction_type = models.CharField(max_length=24, choices=TransactionType.choices, db_index=True)
    direction = models.CharField(max_length=6, choices=Direction.choices)
    balance_type = models.CharField(max_length=12, choices=BalanceType.choices)
    amount = money_field()
    reference_type = models.CharField(max_length=64, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    description = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True)
    idempotency_key = models.CharField(
        max_length=128,
        unique=True,
        null=True,
        blank=True,
        help_text='Optional unique key; a retried job/request with the same key cannot create a second ledger row.',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['transaction_type', '-created_at']),
            models.Index(fields=['reference_type', 'reference_id']),
        ]
        constraints = [
            models.CheckConstraint(check=models.Q(amount__gt=0), name='ledger_amount_positive'),
            models.CheckConstraint(
                check=models.Q(direction__in=['CREDIT', 'DEBIT']),
                name='ledger_direction_valid',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.transaction_id} {self.direction} {self.amount}'


class Network(TimeStampedModel):
    """Blockchain network configuration (BSC, TRX, ETH, POL, SOL, TON).

    Nothing about networks is hard-coded in views or templates; everything
    reads from this table. Per-network deposit/withdrawal parameters
    (contract, minimums, fee, warnings) are admin-editable columns so the
    operator can manage every network without a code change. Empty numeric
    fields fall back to the platform-wide SiteSetting defaults — a value of
    ``None`` means "use the global rule".
    """

    name = models.CharField(max_length=64)
    code = models.CharField(max_length=10, unique=True)
    asset = models.CharField(max_length=10, default='USDT')
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    # --- Per-network production configuration (admin-editable) -----------
    # USDT token/contract identifier on this network (TRC-20 contract,
    # ERC-20/BEP-20/Polygon contract address, Solana mint, …). Display
    # information only — verification still goes through
    # settings.USDT_CONTRACTS when chain verification is enabled.
    contract_address = models.CharField(max_length=255, blank=True)
    # None = inherit the global minimum (deposit.min_amount setting).
    min_deposit = optional_money_field(null=True)
    # None = inherit the global minimum/fee (withdrawal.min_amount etc.).
    min_withdrawal = optional_money_field(null=True)
    withdrawal_fee = optional_money_field(null=True)
    # True/False override; None = follow the global fee model.
    withdrawal_fee_is_percent = models.BooleanField(null=True, blank=True)
    # User-facing copy shown on the deposit/withdraw pages.
    network_warning = models.CharField(max_length=500, blank=True)
    instructions = models.TextField(blank=True)

    class Meta:
        ordering = ['sort_order', 'code']
        constraints = [
            models.UniqueConstraint(fields=['code', 'asset'], name='network_code_asset_unique'),
            models.CheckConstraint(
                check=models.Q(min_deposit__isnull=True) | models.Q(min_deposit__gt=0),
                name='network_min_deposit_positive',
            ),
            models.CheckConstraint(
                check=models.Q(min_withdrawal__isnull=True) | models.Q(min_withdrawal__gt=0),
                name='network_min_withdrawal_positive',
            ),
            models.CheckConstraint(
                check=models.Q(withdrawal_fee__isnull=True) | models.Q(withdrawal_fee__gte=0),
                name='network_withdrawal_fee_nonnegative',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'


class DepositAddress(TimeStampedModel):
    """Receiving addresses per network/asset.

    Multiple historical addresses per network are allowed; only ``is_active``
    rows are shown to users. QR is stored as a path/reference, not binary.
    """

    network = models.ForeignKey(Network, on_delete=models.PROTECT, related_name='deposit_addresses')
    asset = models.CharField(max_length=10, default='USDT')
    address = models.CharField(max_length=255)
    qr_code = models.CharField(max_length=255, blank=True, help_text='Path or URL reference to the QR image.')
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ['-is_active', 'network__sort_order']
        constraints = [
            # Only ONE active address per (network, asset); historical
            # inactive addresses are unlimited.
            models.UniqueConstraint(
                fields=['network', 'asset'],
                condition=models.Q(is_active=True),
                name='depositaddress_unique_active_per_network_asset',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.network.code}/{self.asset}: {self.address[:12]}…'
