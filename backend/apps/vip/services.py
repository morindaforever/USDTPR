"""VIP purchase service.

Business rules live here; views only translate HTTP.

Purchase flow (all inside ONE database transaction):

    validate user/plan/account
      → lock wallet row (wallet service does select_for_update)
      → idempotency check (purchase.idempotency_key unique per user)
      → welcome-claim guard (at most one WELCOME purchase per user)
      → debit investment via wallet service (raises on insufficient funds;
        rolls back everything on any failure)
      → create VIPPurchase with SNAPSHOT of plan terms
      → audit log + notification
      → commit

Concurrency: two simultaneous purchases serialize on the wallet row lock —
the second sees the post-debit balance and is rejected if short.

Idempotency: the wallet debit uses ``VIP_PURCHASE_<user idempotency key>``
as its key, and the purchase row stores the same key; a retry returns the
original purchase without double-debiting.

The daily reward engine is Section 8 — this module creates the purchase
infrastructure only. No reward calculation happens here.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.notifications.services import notify_event
from apps.wallet.services import InsufficientBalanceError, WalletError, debit, get_wallet_summary

from .models import VIPPlan, VIPPurchase


class VIPError(Exception):
    """Domain error with a user-safe message and optional field errors."""

    def __init__(self, message: str, errors: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}


def _validate_account(user: User) -> None:
    if user.account_status == User.AccountStatus.BANNED:
        raise VIPError('This account cannot make purchases.')
    if user.account_status == User.AccountStatus.SUSPENDED:
        raise VIPError('This account is suspended. Contact support.')


def _get_active_plan(plan_id) -> VIPPlan:
    try:
        plan = VIPPlan.objects.get(pk=plan_id)
    except (VIPPlan.DoesNotExist, ValueError, TypeError) as exc:
        raise VIPError('Plan not found.', {'plan_id': ['Plan not found.']}) from exc
    if not plan.is_active:
        raise VIPError('This plan is currently unavailable.', {'plan_id': ['This plan is currently unavailable.']})
    return plan


def _check_welcome_claim(user: User, plan: VIPPlan) -> None:
    """At most one WELCOME-plan purchase per user, ever (any status)."""
    if plan.name.upper().startswith('WELCOME'):
        if VIPPurchase.objects.filter(user=user, vip_plan=plan).exists():
            raise VIPError(
                'The Welcome plan has already been claimed on this account.',
                {'plan_id': ['Welcome plan can only be claimed once.']},
            )


@dataclass
class PurchaseResult:
    purchase: VIPPurchase
    already_existed: bool = False


@transaction.atomic
def purchase_plan(*, user: User, plan_id, idempotency_key: str = '') -> PurchaseResult:
    """Purchase a VIP plan using the user's withdrawable balance.

    Authoritative amounts ALWAYS come from the VIPPlan row — never from the
    request. Any failure at any step rolls back the whole operation.
    """
    _validate_account(user)
    plan = _get_active_plan(plan_id)
    _check_welcome_claim(user, plan)

    key = (idempotency_key or '').strip()
    if not key:
        raise VIPError(
            'An idempotency key is required for purchases.',
            {'idempotency_key': ['This field is required.']},
        )
    if len(key) > 100:
        raise VIPError(
            'Idempotency key is too long.',
            {'idempotency_key': ['Maximum length is 100 characters.']},
        )

    # Idempotent replay: return the existing purchase if this key was used.
    existing = VIPPurchase.objects.filter(user=user, idempotency_key=key).first()
    if existing is not None:
        return PurchaseResult(purchase=existing, already_existed=True)

    # Wallet ledger keys are globally unique, so derive a per-user key.
    wallet_key = f'VIP_PURCHASE_{user.pk}_{key}'

    # Debit through the wallet service (locks the wallet row; raises
    # InsufficientBalanceError with no money moved). The ledger row this
    # creates references the purchase via reference fields set below — but
    # the purchase row must exist first for its ID, so we create the
    # purchase BEFORE the debit while still inside the same transaction:
    # if the debit fails, the purchase creation rolls back too.
    purchase = VIPPurchase(
        user=user,
        vip_plan=plan,
        status=VIPPurchase.Status.PENDING,
        idempotency_key=key,
    )
    # save() snapshots plan terms on first save.
    try:
        purchase.save()
    except IntegrityError as exc:
        # Concurrent duplicate welcome-claim: the per-user partial unique
        # constraint (WELCOME_CLAIM_* keys) fires here for the losing
        # request. Raise as a domain error so the transaction rolls back.
        raise VIPError(
            'The Welcome plan has already been claimed on this account.',
            {'plan_id': ['Welcome plan can only be claimed once.']},
        ) from exc

    # Zero-investment (WELCOME/free-plan) claims move no balance, so there is
    # nothing to debit and no ledger row — the claim guard + purchase
    # idempotency key protect them instead.
    if purchase.investment_amount > 0:
        try:
            debit(
                user=user,
                amount=purchase.investment_amount,
                balance_type='WITHDRAWABLE',
                transaction_type='VIP_PURCHASE',
                reference_type='vip_purchase',
                reference_id=purchase.purchase_id,
                description=f'VIP plan {purchase.plan_name_snapshot} purchase',
                idempotency_key=wallet_key,
            )
        except InsufficientBalanceError as exc:
            # Translate into the VIP domain error → 400 with safe message.
            raise VIPError(
                'Insufficient withdrawable balance for this plan.',
                {'balance': ['Insufficient withdrawable balance for this plan.']},
            ) from exc
        except WalletError as exc:
            # Any other wallet failure → roll back purchase too.
            raise VIPError('Unable to complete the purchase. Please try again.') from exc

    purchase.status = VIPPurchase.Status.ACTIVE
    purchase.started_at = timezone.now()
    purchase.save(update_fields=['status', 'started_at', 'updated_at'])

    AuditLog.objects.create(
        actor_user=user,
        action=AuditLog.Action.CREATE,
        target_type='vip_purchase',
        target_id=purchase.purchase_id,
        description=(
            f'Purchased {purchase.plan_name_snapshot} for {purchase.investment_amount} USDT '
            f'(investment), target {purchase.target_amount} USDT.'
        ),
    )
    notify_event(
        user=user,
        notification_type=Notification.NotificationType.VIP,
        title='VIP Plan Activated',
        message=f'{purchase.plan_name_snapshot} has been activated successfully.',
        event_key=f'vip_purchase:{purchase.purchase_id}:activated',
        related_type='vip_purchase',
        related_id=purchase.purchase_id,
    )
    return PurchaseResult(purchase=purchase)


def plan_purchase_summary(user: User, plan: VIPPlan) -> dict:
    """Authoritative data for the purchase-confirmation modal."""
    summary = get_wallet_summary(user)
    available = summary['withdrawable_balance']
    return {
        'available_balance': available,
        'balance_after_purchase': (available - plan.investment_amount).quantize(Decimal('0.00000001')),
        'sufficient': available >= plan.investment_amount,
    }
