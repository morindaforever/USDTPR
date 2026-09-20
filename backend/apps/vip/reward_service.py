"""VIP reward engine (Section 8) — the ONLY way VIP rewards are credited.

Architecture (per Section 8 §2) — no direct wallet mutation anywhere here:

    Celery beat / management command
        → process_daily_rewards(cycle)
            → process_reward(purchase, cycle)      [this module]
                → wallet service credit()           (Section 5)
                    → wallet ledger row
                    → wallet balance

FLOW per purchase, all inside ONE ``transaction.atomic`` block:

    BEGIN → lock VIPPurchase row (select_for_update)
          → status gate (only ACTIVE pays; COMPLETED/CANCELLED/… skip)
          → start-date gate (no rewards before activation cycle)
          → cycle gate (UNIQUE(purchase, reward_date) + last_reward_cycle
            marker for target-cap-zero cycles)
          → retry reclaim (a PENDING/FAILED row from an earlier crash is
            reprocessed, never duplicated)
          → target cap: actual = min(daily, remaining target)
          → create VIPReward (PENDING)
          → wallet_service.credit(...)  (idempotency key
            VIP_REWARD_<purchase_id>_<cycle>; nested savepoint)
          → VIPReward → COMPLETED (credited amount, txn reference)
          → VIPPurchase.amount_received += credited; COMPLETED at target
          → audit log + notification
    COMMIT

If the wallet credit raises, the VIPReward row is committed as FAILED
(separate savepoint semantics: the failure is recorded, no money moved)
and :class:`RewardProcessingError` is raised for the caller to log/retry.

Idempotency & concurrency (§15–17): the deterministic wallet key plus the
DB unique constraint on (vip_purchase, reward_date) plus row locking mean
double beat ticks, Celery retries, and racing workers can never credit a
cycle twice. A retry detects the existing COMPLETED reward and skips.

All amounts are Decimal at the project's 8-dp wallet precision (§5).
Cycle dates come from Django's timezone config via ``timezone.localdate``
(§9–10) — never ``datetime.now()``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import DecimalField, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.notifications.services import notify_event
from apps.wallet.models import WalletTransaction
from apps.wallet.services import WalletError, credit

from .models import VIPPurchase, VIPReward

logger = logging.getLogger('vip.rewards')

QUANT = Decimal('0.00000001')


class RewardProcessingError(Exception):
    """A reward could not be credited (wallet failure, invalid state…).

    Message is safe for logs; it never reaches API users directly.
    """


def current_cycle() -> date:
    """Today's reward cycle date in the project timezone (§9, §10)."""
    return timezone.localdate()


def reward_idempotency_key(purchase_id: str, cycle_date: date) -> str:
    """Deterministic key so retries can never double-credit (§16)."""
    return f'VIP_REWARD_{purchase_id}_{cycle_date.isoformat()}'


def calculate_daily_reward(purchase: VIPPurchase) -> Decimal:
    """investment × daily_rate from the purchase SNAPSHOT (§4, §58).

    Never reads the current VIPPlan — edited plan terms must not rewrite
    history for existing purchases.
    """
    reward = (purchase.investment_amount * purchase.daily_rate_snapshot).quantize(
        QUANT, rounding=ROUND_HALF_UP
    )
    if reward < 0:  # defensive: DB constraints already forbid negative terms
        raise RewardProcessingError('Calculated reward is negative — refusing to process.')
    return reward


def get_rewarded_amount(purchase: VIPPurchase) -> Decimal:
    """Sum of COMPLETED credited rewards (§23) — falls back to the
    transactionally-maintained ``amount_received`` if no rows exist yet."""
    total = purchase.rewards.filter(status=VIPReward.Status.COMPLETED).aggregate(
        total=Coalesce(Sum('credited_amount'), Decimal('0'), output_field=DecimalField())
    )['total']
    return (total or Decimal('0')).quantize(QUANT)


def get_remaining_target(purchase: VIPPurchase) -> Decimal:
    """target − rewarded, never negative (§6, §23)."""
    remaining = purchase.target_amount - get_rewarded_amount(purchase)
    return max(Decimal('0'), remaining).quantize(QUANT)


def is_eligible_for_cycle(purchase: VIPPurchase, cycle_date: date) -> bool:
    """Eligibility gates that can be checked without locking (§11, §12)."""
    if purchase.status != VIPPurchase.Status.ACTIVE:
        return False
    if purchase.last_reward_cycle is not None and purchase.last_reward_cycle >= cycle_date:
        return False
    if purchase.started_at is not None:
        # No rewards before the activation cycle.
        if timezone.localdate(purchase.started_at) > cycle_date:
            return False
    return True


def calculate_reward_for_cycle(purchase: VIPPurchase, cycle_date: date) -> Decimal:
    """Actual creditable amount for a cycle: min(daily, remaining) (§6)."""
    if not is_eligible_for_cycle(purchase, cycle_date):
        return Decimal('0')
    # A completed row for this cycle means it already paid.
    already_paid = VIPReward.objects.filter(
        vip_purchase=purchase, reward_date=cycle_date, status=VIPReward.Status.COMPLETED,
    ).exists()
    if already_paid:
        return Decimal('0')
    return min(calculate_daily_reward(purchase), get_remaining_target(purchase))


@dataclass
class RewardOutcome:
    """Result of one process_reward call (for logs, tests, and callers)."""

    status: str  # 'credited' | 'already_credited' | 'completed_purchase' | 'skipped' | 'failed'
    reason: str = ''
    reward: VIPReward | None = None
    credited_amount: Decimal = Decimal('0')


def _fire_referral_commissions(reward_id: str) -> None:
    """Post-commit hook: hand a credited reward to the Section 9 engine.

    Commission failures never break reward processing — the referral
    service records failures per ancestor and logs them.
    """
    try:
        from apps.referrals.commission_service import process_referral_commission

        process_referral_commission(reward_id)
    except Exception:  # noqa: BLE001 — hooks must not break the reward run
        logger.exception('Referral commission processing failed for reward %s', reward_id)


def process_reward(purchase_id, cycle_date: date | None = None) -> RewardOutcome:
    """Process one purchase's reward for one cycle, atomically (§14).

    Safe to call repeatedly for the same (purchase, cycle): the first
    success credits; every later call is a no-op. Concurrent callers
    serialize on the purchase row lock; losers observe the committed
    reward and skip.
    """
    cycle = cycle_date or current_cycle()

    failure: WalletError | None = None
    outcome = RewardOutcome(status='skipped')

    with transaction.atomic():
        purchase = (
            VIPPurchase.objects.select_for_update().select_related('user').get(pk=purchase_id)
        )

        # --- status gate -------------------------------------------------
        if purchase.status != VIPPurchase.Status.ACTIVE:
            outcome.reason = f'purchase-status-{purchase.status.lower()}'
            return outcome

        # --- start-date gate (§12) ---------------------------------------
        if purchase.started_at is not None and timezone.localdate(purchase.started_at) > cycle:
            outcome.reason = 'before-start-date'
            return outcome

        # --- cycle gate: already fully consumed by the target cap (§6) ---
        if purchase.last_reward_cycle is not None and purchase.last_reward_cycle >= cycle:
            outcome.reason = 'cycle-consumed-by-target-cap'
            return outcome

        # --- retry / duplicate handling (§17) ----------------------------
        existing = VIPReward.objects.select_for_update().filter(
            vip_purchase=purchase, reward_date=cycle,
        ).first()
        if existing is not None and existing.status == VIPReward.Status.COMPLETED:
            # Section 9: re-fire commissions on retries too — the engine is
            # idempotent per (reward, beneficiary, level), so this only
            # retries commissions that previously FAILED.
            transaction.on_commit(
                lambda rid=existing.reward_id: _fire_referral_commissions(rid)
            )
            return RewardOutcome(
                status='already_credited',
                reason='duplicate-retry',
                reward=existing,
                credited_amount=existing.credited_amount,
            )
        if existing is not None and existing.status == VIPReward.Status.REVERSED:
            outcome.reason = 'reward-reversed'
            return outcome
        # A PENDING row means a previous attempt crashed mid-transaction;
        # a FAILED row means the wallet credit failed earlier. Both are
        # reclaimed and reprocessed here — never duplicated.

        remaining = get_remaining_target(purchase)
        calculated = calculate_daily_reward(purchase)
        actual = min(calculated, remaining)

        if actual <= 0:
            # No credit is due this cycle (zero-investment plan or target
            # already met): mark the cycle consumed so it can never pay
            # again (no VIPReward row for it — the unique constraint alone
            # can't express this).
            purchase.last_reward_cycle = cycle
            purchase.save(update_fields=['last_reward_cycle', 'updated_at'])
            AuditLog.objects.create(
                actor_user=None,
                action=AuditLog.Action.OTHER,
                target_type='vip_purchase',
                target_id=purchase.purchase_id,
                description=f'Reward cycle {cycle.isoformat()} closed with no credit due (target cap or zero-reward plan).',
            )
            outcome.reason = 'no-credit-due'
            return outcome

        user = purchase.user
        reward = existing or VIPReward(
            user=user,
            vip_purchase=purchase,
            reward_date=cycle,
            calculated_amount=calculated,
        )
        reward.calculated_amount = calculated
        reward.status = VIPReward.Status.PENDING
        reward.error_info = ''
        reward.save()

        # --- wallet credit through the Section 5 service (§18) ------------
        try:
            txn = credit(
                user=user,
                amount=actual,
                balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
                transaction_type=WalletTransaction.TransactionType.VIP_REWARD,
                reference_type='vip_reward',
                reference_id=reward.reward_id,
                description=f'VIP reward — {purchase.plan_name_snapshot} — cycle {cycle.isoformat()}'[:255],
                idempotency_key=reward_idempotency_key(purchase.purchase_id, cycle),
            )
        except WalletError as exc:
            # Record the FAILED row (committed when the block exits) but do
            # NOT credit anything and DO mark the caller-visible failure.
            reward.status = VIPReward.Status.FAILED
            reward.error_info = (exc.message or 'wallet-credit-failed')[:255]
            reward.processed_at = timezone.now()
            reward.save()
            AuditLog.objects.create(
                actor_user=None,
                action=AuditLog.Action.OTHER,
                target_type='vip_reward',
                target_id=reward.reward_id,
                description=f'Reward processing failed for cycle {cycle.isoformat()} (wallet error).',
            )
            failure = exc
        else:
            reward.status = VIPReward.Status.COMPLETED
            reward.credited_amount = actual
            reward.wallet_transaction = txn
            reward.processed_at = timezone.now()
            reward.save()

            # Progress + completion, atomically with the credit (§13, §23).
            # The rewards ledger is authoritative: recompute the total from
            # COMPLETED reward rows (self-healing against any historical
            # drift) and mirror it into the denormalized amount_received.
            total_rewarded = get_rewarded_amount(purchase)
            purchase.amount_received = total_rewarded
            completed = total_rewarded >= purchase.target_amount
            if completed:
                purchase.status = VIPPurchase.Status.COMPLETED
                purchase.completed_at = timezone.now()
            purchase.save(
                update_fields=['amount_received', 'status', 'completed_at', 'updated_at']
            )

            AuditLog.objects.create(
                actor_user=None,
                action=AuditLog.Action.OTHER,
                target_type='vip_reward',
                target_id=reward.reward_id,
                description=(
                    f'VIP reward {actual} USDT credited for {purchase.plan_name_snapshot} '
                    f'(cycle {cycle.isoformat()}, purchase {purchase.purchase_id}).'
                ),
            )
            notify_event(
                user=user,
                notification_type=Notification.NotificationType.REWARD,
                title='Reward Credited',
                message=(
                    f'{actual.quantize(Decimal("0.01"))} USDT has been credited to your wallet '
                    f'for {purchase.plan_name_snapshot}.'
                ),
                event_key=f'reward:{reward.reward_id}:credited',
                related_type='vip_reward',
                related_id=reward.reward_id,
            )
            if completed:
                notify_event(
                    user=user,
                    notification_type=Notification.NotificationType.VIP,
                    title='VIP plan completed',
                    message=(
                        f'Your {purchase.plan_name_snapshot} plan has reached its target.'
                    ),
                    event_key=f'vip_purchase:{purchase.purchase_id}:completed',
                    related_type='vip_purchase',
                    related_id=purchase.purchase_id,
                )
            # Section 9 §18/§45: commissions are paid from eligible VIP
            # reward credits, after this transaction commits. The referral
            # engine is idempotent per (reward, beneficiary, level).
            transaction.on_commit(
                lambda rid=reward.reward_id: _fire_referral_commissions(rid)
            )
            outcome = RewardOutcome(
                status='completed_purchase' if completed else 'credited',
                reward=reward,
                credited_amount=actual,
            )

    if failure is not None:
        logger.warning(
            'Reward credit failed purchase=%s cycle=%s: %s',
            purchase_id, cycle.isoformat(), failure,
        )
        raise RewardProcessingError(f'Wallet credit failed for cycle {cycle.isoformat}.') from failure
    return outcome


# Spec §25 alias — same operation, clearer name for task/command callers.
process_purchase_reward = process_reward


def eligible_purchases(cycle_date: date):
    """Queryset of purchases eligible for a cycle (batched IDs at call sites).

    Selects only what processing needs; ordering gives deterministic runs
    and simplifies log reading. Batching keeps memory flat as volume grows.
    """
    return (
        VIPPurchase.objects.filter(status=VIPPurchase.Status.ACTIVE)
        .filter(Q(started_at__isnull=True) | Q(started_at__date__lte=cycle_date))
        .exclude(last_reward_cycle__gte=cycle_date)
        .select_related('user')
        .only(
            'id', 'purchase_id', 'user__id', 'plan_name_snapshot', 'investment_amount',
            'target_amount', 'daily_rate_snapshot', 'amount_received', 'status',
            'started_at', 'last_reward_cycle',
        )
        .order_by('id')
    )


def process_daily_rewards(cycle_date: date | None = None, batch_size: int = 500) -> dict:
    """Process every eligible purchase for a cycle (§26).

    One purchase failing (wallet error, data issue) never stops the run:
    failures are logged and counted, the loop continues. Re-running the
    whole batch is safe — credited cycles skip as duplicates.
    """
    cycle = cycle_date or current_cycle()
    stats = {'cycle': cycle.isoformat(), 'eligible': 0, 'credited': 0, 'completed': 0,
             'skipped': 0, 'failed': 0}

    purchase_ids = list(
        eligible_purchases(cycle).values_list('id', flat=True)[:100_000]
    )
    stats['eligible'] = len(purchase_ids)
    logger.info('Reward run started cycle=%s eligible=%d', cycle.isoformat(), len(purchase_ids))

    for start in range(0, len(purchase_ids), batch_size):
        for purchase_id in purchase_ids[start:start + batch_size]:
            try:
                outcome = process_reward(purchase_id, cycle)
            except RewardProcessingError as exc:
                stats['failed'] += 1
                logger.error('Reward failed purchase=%s cycle=%s: %s', purchase_id, cycle, exc)
                continue
            if outcome.status == 'credited':
                stats['credited'] += 1
            elif outcome.status == 'completed_purchase':
                stats['credited'] += 1
                stats['completed'] += 1
            elif outcome.status == 'already_credited':
                stats['skipped'] += 1
            else:
                stats['skipped'] += 1

    logger.info(
        'Reward run finished cycle=%s credited=%d completed=%d skipped=%d failed=%d',
        cycle.isoformat(), stats['credited'], stats['completed'], stats['skipped'], stats['failed'],
    )
    return stats


def next_reward_at() -> datetime:
    """The next scheduled Celery beat run as an aware datetime (§35).

    Mirrors CELERY_BEAT_SCHEDULE (00:15 project time) so any UI countdown
    shares one source of truth with the actual scheduler.
    """
    now = timezone.localtime()
    run = now.replace(hour=0, minute=15, second=0, microsecond=0)
    if run <= now:
        run += timedelta(days=1)
    return run


def get_purchase_progress(purchase: VIPPurchase, rewarded: Decimal | None = None) -> dict:
    """Backend-authoritative progress numbers for one purchase (§22, §23).

    ``rewarded`` may carry a pre-aggregated sum (``active_purchases_with_progress``
    annotation) to avoid a per-row query; otherwise it is computed here.

    Zero-investment WELCOME grants are credited once at claim time (mirrored
    into ``amount_received``) without daily VIPReward rows, so the reported
    total is never less than the transactionally-maintained amount.
    """
    rewarded = get_rewarded_amount(purchase) if rewarded is None else rewarded.quantize(QUANT)
    rewarded = max(rewarded, purchase.amount_received.quantize(QUANT))
    remaining = max(Decimal('0'), purchase.target_amount - rewarded).quantize(QUANT)
    target = purchase.target_amount
    percent = (rewarded / target * 100) if target > 0 else Decimal('100')
    return {
        'rewarded_amount': str(rewarded),
        'remaining_amount': str(remaining),
        'progress_percent': str(min(Decimal('100'), percent).quantize(Decimal('0.01'))),
        'next_reward_cycle': (current_cycle() + timedelta(days=1)).isoformat(),
        'next_reward_at': next_reward_at().isoformat(),
    }


def active_purchases_with_progress(user):
    """The user's ACTIVE/COMPLETED purchases annotated with rewarded totals.

    Single aggregated query — no per-purchase reward sums (§49).
    """
    return (
        VIPPurchase.objects.filter(user=user, status__in=[
            VIPPurchase.Status.ACTIVE, VIPPurchase.Status.COMPLETED,
        ])
        .annotate(
            rewarded_amount_annotated=Coalesce(
                Sum('rewards__credited_amount', filter=Q(rewards__status=VIPReward.Status.COMPLETED)),
                Decimal('0'),
                output_field=DecimalField(),
            ),
        )
        .select_related('vip_plan')
        .order_by('-created_at')
    )
