"""VIP reward engine tests (Section 8).

Covers: Decimal calculations per plan, target cap + completion, duplicate
processing, concurrency, retry/reclaim safety, wallet-failure rollback,
plan-snapshot terms, status/start-date gates, user isolation, API
authorization, and three-way accounting invariants
(VIPReward = WalletTransaction = wallet balance delta).
"""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from threading import Barrier
from unittest import mock

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.vip.models import VIPPlan, VIPPurchase, VIPReward
from apps.vip.reward_service import (
    RewardProcessingError,
    calculate_daily_reward,
    calculate_reward_for_cycle,
    current_cycle,
    get_purchase_progress,
    get_remaining_target,
    process_daily_rewards,
    process_reward,
)
from apps.vip.services import purchase_plan
from apps.wallet.models import Wallet, WalletTransaction
from apps.wallet.services import credit

TT = WalletTransaction.TransactionType
D8 = Decimal('0.00000001')


class RewardTestBase(TestCase):
    """Funded user + second (isolation) user + seeded plans."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', stdout=None, verbosity=0)
        cls.plan1 = VIPPlan.objects.get(name='VIP 1')
        cls.plan2 = VIPPlan.objects.get(name='VIP 2')

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='reward@example.com', password='S3curePass!', phone='+15550800001', full_name='Reward User'
        )
        self.other = User.objects.create_user(
            email='rewardother@example.com', password='S3curePass!', phone='+15550800002', full_name='Other User'
        )
        Wallet.objects.create(user=self.user)
        Wallet.objects.create(user=self.other)
        self.cycle = current_cycle()

    def wallet(self) -> Wallet:
        return Wallet.objects.get(user=self.user)

    def refresh(self) -> None:
        self.wallet().refresh_from_db()


class CalculationTests(RewardTestBase):
    """§4/§5/§51 — investment × rate per plan, Decimal-exact."""

    def _purchase(self, plan: VIPPlan, user=None, amount=None, target=None) -> VIPPurchase:
        invest = Decimal(amount) if amount else None
        p = VIPPurchase(
            user=user or self.user,
            vip_plan=plan,
            plan_name_snapshot=plan.name,
            investment_amount=invest if invest is not None else plan.investment_amount,
            target_amount=Decimal(target) if target else plan.target_amount,
            daily_rate_snapshot=plan.daily_rate,
            status=VIPPurchase.Status.ACTIVE,
        )
        p.save()
        return p

    def test_vip1_daily_is_target_times_rate(self) -> None:
        """VIP 1: target 15 × 25% = 3.75/day — a percentage of TARGET, not investment."""
        p = self._purchase(self.plan1)
        self.assertEqual(calculate_daily_reward(p), Decimal('3.75000000'))

    def test_vip2_daily_is_target_times_rate(self) -> None:
        """VIP 2: target 30 × 25% = 7.50/day."""
        p = self._purchase(self.plan2)
        self.assertEqual(calculate_daily_reward(p), Decimal('7.50000000'))

    def test_daily_uses_target_not_investment(self) -> None:
        """Issue 1 regression guard: investment ≠ target → rate applies to target.

        Investment 10, target 50, rate 10% → daily 5 (NOT 10 × 10% = 1).
        """
        p = self._purchase(self.plan1, target='50')
        VIPPurchase.objects.filter(pk=p.pk).update(daily_rate_snapshot=Decimal('0.1000'))
        p.refresh_from_db()
        self.assertEqual(calculate_daily_reward(p), Decimal('5.00000000'))

    def test_snapshot_not_plan_terms(self) -> None:
        """Edited plan terms must NOT change an existing purchase's calc (§58)."""
        p = self._purchase(self.plan1)
        VIPPlan.objects.filter(pk=self.plan1.pk).update(daily_rate=Decimal('0.5000'))
        p.refresh_from_db()
        self.assertEqual(calculate_daily_reward(p), Decimal('3.75000000'))
        VIPPlan.objects.filter(pk=self.plan1.pk).update(daily_rate=Decimal('0.2500'))

    def test_decimal_precision_never_float(self) -> None:
        p = self._purchase(self.plan1, target='12.34567890')
        expected = (Decimal('12.34567890') * Decimal('0.25')).quantize(
            D8, rounding=ROUND_HALF_UP
        )
        self.assertEqual(calculate_daily_reward(p), expected)
        self.assertIsInstance(calculate_daily_reward(p), Decimal)


class TargetCapTests(RewardTestBase):
    """§6/§52 — partial credit up to the target, then stop + complete."""

    def setUp(self) -> None:
        super().setUp()
        self.purchase = VIPPurchase.objects.create(
            user=self.user,
            vip_plan=self.plan1,
            plan_name_snapshot=self.plan1.name,
            investment_amount=Decimal('10.00000000'),
            target_amount=Decimal('15.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=VIPPurchase.Status.ACTIVE,
        )

    def _seed_reward(self, purchase, credited: str) -> None:
        VIPReward.objects.create(
            user=purchase.user,
            vip_purchase=purchase,
            reward_date=self.cycle - timedelta(days=1),
            calculated_amount=Decimal(credited),
            credited_amount=Decimal(credited),
            status=VIPReward.Status.COMPLETED,
        )

    def test_remaining_target(self) -> None:
        self.assertEqual(get_remaining_target(self.purchase), Decimal('15.00000000'))
        self._seed_reward(self.purchase, '14.00000000')
        self.assertEqual(get_remaining_target(self.purchase), Decimal('1.00000000'))

    def test_partial_final_credit_and_completion(self) -> None:
        self._seed_reward(self.purchase, '14.00000000')
        outcome = process_reward(self.purchase.id, self.cycle)
        self.assertEqual(outcome.status, 'completed_purchase')
        self.assertEqual(outcome.credited_amount, Decimal('1.00000000'))
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.amount_received, Decimal('15.00000000'))
        self.assertEqual(self.purchase.status, VIPPurchase.Status.COMPLETED)
        self.assertIsNotNone(self.purchase.completed_at)

    def test_no_reward_after_completion(self) -> None:
        self._seed_reward(self.purchase, '15.00000000')
        VIPPurchase.objects.filter(pk=self.purchase.pk).update(
            amount_received=Decimal('15.00000000'), status=VIPPurchase.Status.COMPLETED,
            completed_at=timezone.now(),
        )
        outcome = process_reward(self.purchase.id, self.cycle)
        self.assertEqual(outcome.status, 'skipped')
        self.assertFalse(VIPReward.objects.filter(reward_date=self.cycle, vip_purchase=self.purchase).exists())

    def test_welcome_plan_daily_progression_issue9(self) -> None:
        """Issue 9 — Welcome plan (target 10, 25%): 2.5/day, 4 cycles, then done.

        Activation credits nothing; the plan runs the normal daily lifecycle
        and completes exactly at target.
        """
        welcome = VIPPlan.objects.get(plan_number=0)
        p = VIPPurchase.objects.create(
            user=self.user,
            vip_plan=welcome,
            plan_name_snapshot=welcome.name,
            investment_amount=Decimal('0.00000000'),
            target_amount=Decimal('10.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=VIPPurchase.Status.ACTIVE,
        )
        before = self.wallet().withdrawable_balance
        rewarded = Decimal('0')
        for day in range(1, 6):
            outcome = process_reward(p.id, self.cycle + timedelta(days=day))
            p.refresh_from_db()
            if day <= 4:
                self.assertIn(outcome.status, ('credited', 'completed_purchase'), day)
                self.assertEqual(outcome.credited_amount, Decimal('2.50000000'))
                rewarded += Decimal('2.50000000')
                self.assertEqual(p.amount_received, rewarded)
                self.assertEqual(
                    p.status,
                    VIPPurchase.Status.COMPLETED if day == 4 else VIPPurchase.Status.ACTIVE,
                )
            else:
                # Day 5: target already reached — nothing more is paid.
                self.assertEqual(outcome.status, 'skipped', day)
                self.assertEqual(outcome.reason, 'purchase-status-completed')
        p.refresh_from_db()
        self.assertEqual(p.amount_received, Decimal('10.00000000'))
        self.assertEqual(p.status, VIPPurchase.Status.COMPLETED)
        self.assertIsNotNone(p.completed_at)
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, before + Decimal('10.00000000'))
        # Exactly four COMPLETED reward rows / ledger entries.
        self.assertEqual(VIPReward.objects.filter(vip_purchase=p).count(), 4)
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.user, transaction_type=TT.VIP_REWARD, status=WalletTransaction.Status.COMPLETED,
            ).count(),
            4,
        )

    def test_welcome_plan_activation_credits_nothing(self) -> None:
        """Issue 2 — a claimed welcome plan starts at rewarded=0, no bonus bucket."""
        from apps.vip.services import purchase_plan

        welcome = VIPPlan.objects.get(plan_number=0)
        before = self.wallet().withdrawable_balance
        bonus_before = self.wallet().bonus_balance
        purchase_plan(user=self.user, plan_id=welcome.pk, idempotency_key='WELCOME_CLAIM_issue2')
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, before)
        self.assertEqual(self.wallet().bonus_balance, bonus_before)
        self.assertFalse(
            WalletTransaction.objects.filter(
                user=self.user, transaction_type=TT.WELCOME_BONUS, status=WalletTransaction.Status.COMPLETED,
            ).exists(),
        )

    def test_partial_final_reward_uses_remaining_not_full_daily(self) -> None:
        """Issue 3/§9 — remaining 5 with daily 15 pays exactly 5, not 15."""
        p = VIPPurchase.objects.create(
            user=self.user,
            vip_plan=self.plan1,
            plan_name_snapshot=self.plan1.name,
            investment_amount=Decimal('10.00000000'),
            target_amount=Decimal('50.00000000'),
            daily_rate_snapshot=Decimal('0.3000'),
            status=VIPPurchase.Status.ACTIVE,
        )
        self._seed_reward(p, '45.00000000')
        VIPPurchase.objects.filter(pk=p.pk).update(amount_received=Decimal('45.00000000'))
        outcome = process_reward(p.id, self.cycle)
        self.assertEqual(outcome.status, 'completed_purchase')
        self.assertEqual(outcome.credited_amount, Decimal('5.00000000'))
        p.refresh_from_db()
        self.assertEqual(p.amount_received, Decimal('50.00000000'))
        self.assertEqual(p.status, VIPPurchase.Status.COMPLETED)

    def test_zero_reward_cycle_consumed_exactly_once(self) -> None:
        """A rate of exactly 0 consumes the cycle once and never re-pays."""
        p = VIPPurchase.objects.create(
            user=self.user,
            vip_plan=self.plan1,
            plan_name_snapshot=self.plan1.name,
            investment_amount=Decimal('10.00000000'),
            target_amount=Decimal('15.00000000'),
            daily_rate_snapshot=Decimal('0.0000'),
            status=VIPPurchase.Status.ACTIVE,
        )
        first = process_reward(p.id, self.cycle)
        self.assertEqual(first.status, 'skipped')
        self.assertEqual(first.reason, 'no-credit-due')
        p.refresh_from_db()
        self.assertEqual(p.last_reward_cycle, self.cycle)
        # Later cycle → still nothing (the plan again produces zero credit).
        second = process_reward(p.id, self.cycle + timedelta(days=1))
        self.assertEqual(second.status, 'skipped')
        self.assertEqual(second.reason, 'no-credit-due')
        # A target-cap-consumed cycle behaves the same way.
        self._seed_reward(self.purchase, '15.00000000')
        VIPPurchase.objects.filter(pk=self.purchase.pk).update(
            amount_received=Decimal('15.00000000'), last_reward_cycle=self.cycle,
        )
        again = process_reward(self.purchase.id, self.cycle)
        self.assertEqual(again.status, 'skipped')


class ProcessRewardTests(RewardTestBase):
    """§13/§14/§31 — credit, progress, notification, audit, completion."""

    def setUp(self) -> None:
        super().setUp()
        self.purchase = VIPPurchase.objects.create(
            user=self.user,
            vip_plan=self.plan1,
            plan_name_snapshot=self.plan1.name,
            investment_amount=Decimal('10.00000000'),
            target_amount=Decimal('15.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=VIPPurchase.Status.ACTIVE,
        )

    def test_first_credit_updates_everything(self) -> None:
        before = self.wallet().withdrawable_balance
        outcome = process_reward(self.purchase.id, self.cycle)
        self.assertEqual(outcome.status, 'credited')
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, before + Decimal('3.75000000'))
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.amount_received, Decimal('3.75000000'))
        reward = VIPReward.objects.get(vip_purchase=self.purchase, reward_date=self.cycle)
        self.assertEqual(reward.status, VIPReward.Status.COMPLETED)
        self.assertEqual(reward.credited_amount, Decimal('3.75000000'))
        self.assertIsNotNone(reward.processed_at)
        self.assertTrue(Notification.objects.filter(
            user=self.user, notification_type=Notification.NotificationType.REWARD
        ).exists())
        self.assertTrue(AuditLog.objects.filter(target_type='vip_reward').exists())

    def test_completion_notification(self) -> None:
        VIPReward.objects.create(
            user=self.user, vip_purchase=self.purchase, reward_date=self.cycle - timedelta(days=1),
            calculated_amount=Decimal('14.00000000'), credited_amount=Decimal('14.00000000'),
            status=VIPReward.Status.COMPLETED,
        )
        VIPPurchase.objects.filter(pk=self.purchase.pk).update(amount_received=Decimal('14.00000000'))
        process_reward(self.purchase.id, self.cycle)
        self.assertTrue(Notification.objects.filter(
            user=self.user, title='VIP plan completed'
        ).exists())

    def test_retry_does_not_double_credit(self) -> None:
        """§17/§53 — same cycle twice: one reward, one ledger row, one delta."""
        before = self.wallet().withdrawable_balance
        process_reward(self.purchase.id, self.cycle)
        process_reward(self.purchase.id, self.cycle)
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, before + Decimal('3.75000000'))
        self.assertEqual(VIPReward.objects.filter(vip_purchase=self.purchase).count(), 1)
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.user, transaction_type=TT.VIP_REWARD, status=WalletTransaction.Status.COMPLETED,
            ).count(),
            1,
        )

    def test_failed_reward_reclaimed_on_retry(self) -> None:
        """§55/§30 — wallet failure records FAILED; retry succeeds once."""
        before = self.wallet().withdrawable_balance
        with mock.patch('apps.vip.reward_service.credit', side_effect=__import__(
            'apps.wallet.services.errors', fromlist=['WalletError']
        ).WalletError('ledger down')):
            with self.assertRaises(RewardProcessingError):
                process_reward(self.purchase.id, self.cycle)
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, before)  # no corruption
        failed = VIPReward.objects.get(vip_purchase=self.purchase, reward_date=self.cycle)
        self.assertEqual(failed.status, VIPReward.Status.FAILED)
        # Purchase still ACTIVE; retry now succeeds and pays exactly once.
        self.assertEqual(self.purchase.refresh_from_db() or self.purchase.status, VIPPurchase.Status.ACTIVE)
        outcome = process_reward(self.purchase.id, self.cycle)
        self.assertEqual(outcome.status, 'credited')
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, before + Decimal('3.75000000'))
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.user, transaction_type=TT.VIP_REWARD, status=WalletTransaction.Status.COMPLETED,
            ).count(),
            1,
        )

    def test_daily_batch_counts(self) -> None:
        """§26 — batch run credits, continues past failures, and is idempotent."""
        other_purchase = VIPPurchase.objects.create(
            user=self.other,
            vip_plan=self.plan2,
            plan_name_snapshot=self.plan2.name,
            investment_amount=Decimal('20.00000000'),
            target_amount=Decimal('30.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=VIPPurchase.Status.ACTIVE,
        )
        stats = process_daily_rewards(self.cycle)
        self.assertEqual(stats['credited'], 2)
        self.assertEqual(stats['completed'], 0)
        # Re-run: everything skips, no double credit.
        stats2 = process_daily_rewards(self.cycle)
        self.assertEqual(stats2['credited'], 0)
        self.assertEqual(stats2['skipped'], 2)


class StatusGateTests(RewardTestBase):
    """§59 — only ACTIVE purchases pay."""

    def _purchase_with_status(self, status: str) -> VIPPurchase:
        return VIPPurchase.objects.create(
            user=self.user,
            vip_plan=self.plan1,
            plan_name_snapshot=self.plan1.name,
            investment_amount=Decimal('10.00000000'),
            target_amount=Decimal('15.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=status,
        )

    def test_only_active_pays(self) -> None:
        eligible = []
        for status in ['ACTIVE', 'COMPLETED', 'CANCELLED', 'PENDING']:
            p = self._purchase_with_status(status)
            outcome = process_reward(p.id, self.cycle)
            if outcome.status in ('credited', 'completed_purchase'):
                eligible.append(status)
            elif status == 'ACTIVE':
                self.fail('ACTIVE purchase did not receive a reward')
        self.assertEqual(eligible, ['ACTIVE'])
        self.assertEqual(VIPReward.objects.count(), 1)

    def test_future_start_date_pays_nothing_until_active(self) -> None:
        """§12/§60 — no rewards before the activation cycle."""
        future = self.cycle + timedelta(days=3)
        p = self._purchase_with_status('ACTIVE')
        VIPPurchase.objects.filter(pk=p.pk).update(
            started_at=timezone.make_aware(timezone.datetime.combine(future, timezone.datetime.min.time())),
        )
        outcome = process_reward(p.id, self.cycle)
        self.assertEqual(outcome.status, 'skipped')
        self.assertEqual(outcome.reason, 'before-start-date')
        # After the start cycle arrives, the purchase pays normally.
        later = process_reward(p.id, future)
        self.assertEqual(later.status, 'credited')

    def test_calculate_for_cycle_respects_gates(self) -> None:
        p = self._purchase_with_status('PENDING')
        self.assertEqual(calculate_reward_for_cycle(p, self.cycle), Decimal('0'))


class AccountingTests(RewardTestBase):
    """§39/§62 — VIPReward = WalletTransaction = wallet delta, always."""

    def setUp(self) -> None:
        super().setUp()
        self.purchase = VIPPurchase.objects.create(
            user=self.user,
            vip_plan=self.plan2,
            plan_name_snapshot=self.plan2.name,
            investment_amount=Decimal('20.00000000'),
            target_amount=Decimal('30.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=VIPPurchase.Status.ACTIVE,
        )

    def test_three_way_agreement(self) -> None:
        before = self.wallet().withdrawable_balance
        process_reward(self.purchase.id, self.cycle)
        self.refresh()
        reward = VIPReward.objects.get(vip_purchase=self.purchase, reward_date=self.cycle)
        txn = reward.wallet_transaction
        self.assertEqual(txn.transaction_type, TT.VIP_REWARD)
        self.assertEqual(txn.direction, WalletTransaction.Direction.CREDIT)
        self.assertEqual(txn.reference_id, reward.reward_id)
        self.assertEqual(txn.amount, reward.credited_amount)
        self.assertEqual(
            self.wallet().withdrawable_balance - before, reward.credited_amount
        )
        self.assertIn('VIP reward', txn.description)

    def test_progress_matches_rewards(self) -> None:
        process_reward(self.purchase.id, self.cycle)
        self.purchase.refresh_from_db()
        progress = get_purchase_progress(self.purchase)
        self.assertEqual(Decimal(progress['rewarded_amount']), Decimal('7.50000000'))
        self.assertEqual(Decimal(progress['remaining_amount']), Decimal('22.50000000'))
        self.assertEqual(Decimal(progress['progress_percent']), Decimal('25.00'))
        self.assertEqual(progress['next_reward_cycle'], (self.cycle + timedelta(days=1)).isoformat())


class RewardApiTests(RewardTestBase):
    """§20/§21/§57/§61 — history, detail, isolation, authorization."""

    def setUp(self) -> None:
        super().setUp()
        self.purchase = VIPPurchase.objects.create(
            user=self.user,
            vip_plan=self.plan1,
            plan_name_snapshot=self.plan1.name,
            investment_amount=Decimal('10.00000000'),
            target_amount=Decimal('15.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=VIPPurchase.Status.ACTIVE,
        )
        self.other_purchase = VIPPurchase.objects.create(
            user=self.other,
            vip_plan=self.plan1,
            plan_name_snapshot=self.plan1.name,
            investment_amount=Decimal('10.00000000'),
            target_amount=Decimal('15.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=VIPPurchase.Status.ACTIVE,
        )
        process_reward(self.purchase.id, self.cycle)
        self.reward = VIPReward.objects.get(vip_purchase=self.purchase, reward_date=self.cycle)

    def _auth(self, user: User) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

        token = str(RefreshToken.for_user(user).access_token)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {token}'

    def test_reward_history_own_rows_only(self) -> None:
        self._auth(self.user)
        res = self.client.get(reverse('vip:rewards'))
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body['success'])
        self.assertEqual(body['pagination']['count'], 1)
        row = body['data'][0]
        self.assertEqual(row['reward_id'], self.reward.reward_id)
        self.assertEqual(row['plan_name'], 'VIP 1')
        self.assertEqual(row['transaction_id'], self.reward.wallet_transaction.transaction_id)

    def test_reward_history_requires_auth(self) -> None:
        self.assertEqual(self.client.get(reverse('vip:rewards')).status_code, 401)

    def test_reward_detail_owner_only(self) -> None:
        self._auth(self.user)
        res = self.client.get(reverse('vip:reward-detail', args=[self.reward.reward_id]))
        self.assertEqual(res.status_code, 200)
        # User B cannot read User A's reward; invalid ID 404s too.
        self._auth(self.other)
        res = self.client.get(reverse('vip:reward-detail', args=[self.reward.reward_id]))
        self.assertEqual(res.status_code, 404)
        self._auth(self.user)
        res = self.client.get(reverse('vip:reward-detail', args=['REWdoesnotexist']))
        self.assertEqual(res.status_code, 404)

    def test_active_endpoint_exposes_progress(self) -> None:
        self._auth(self.user)
        res = self.client.get(reverse('vip:active'))
        self.assertEqual(res.status_code, 200)
        row = next(r for r in res.json()['data'] if r['purchase_id'] == self.purchase.purchase_id)
        self.assertEqual(Decimal(row['rewarded_amount']), Decimal('3.75000000'))
        self.assertEqual(Decimal(row['remaining_amount']), Decimal('11.25000000'))
        self.assertEqual(Decimal(row['progress_percent']), Decimal('25.00'))

    def test_no_public_reward_trigger(self) -> None:
        """Users cannot trigger processing; the engine is server-side only."""
        self._auth(self.user)
        res = self.client.post('/api/vip/rewards/process/', {}, format='json')
        self.assertIn(res.status_code, (404, 405))


class RewardConcurrencyBase(TransactionTestCase):
    """Threaded tests need committed rows (TestCase wraps in a transaction).

    TransactionTestCase flushes tables between tests, so fixtures are
    created per-test with ``get_or_create`` instead of ``setUpTestData``.
    """

    def setUp(self) -> None:
        plan, _ = VIPPlan.objects.get_or_create(
            name='VIP 1',
            defaults={
                'plan_number': 1,
                'investment_amount': Decimal('10.00000000'),
                'target_amount': Decimal('15.00000000'),
                'daily_rate': Decimal('0.2500'),
                'is_active': True,
                'sort_order': 1,
            },
        )
        self.user = User.objects.create_user(
            email='rewardconc@example.com', password='S3curePass!', phone='+15550800011', full_name='Conc'
        )
        Wallet.objects.create(user=self.user)
        self.purchase = VIPPurchase.objects.create(
            user=self.user,
            vip_plan=plan,
            plan_name_snapshot='VIP 1',
            investment_amount=Decimal('10.00000000'),
            target_amount=Decimal('15.00000000'),
            daily_rate_snapshot=Decimal('0.2500'),
            status=VIPPurchase.Status.ACTIVE,
        )
        self.cycle = current_cycle()

    def _run_parallel(self, fns):
        from concurrent.futures import ThreadPoolExecutor

        def runner(fn):
            try:
                barrier_before, result = fn
                barrier_before.wait()
                return result(), None
            except Exception as exc:  # noqa: BLE001 - collected below
                return None, exc
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=len(fns)) as pool:
            return list(pool.map(runner, fns))


class RewardConcurrencyTests(RewardConcurrencyBase):
    """§54 — racing workers can never credit the same cycle twice."""

    def test_parallel_processing_single_credit(self) -> None:
        barrier = Barrier(2)

        def make_fn():
            def run():
                return process_reward(self.purchase.id, self.cycle)

            return (barrier, run)

        results = self._run_parallel([make_fn(), make_fn()])
        credited = [
            out for out, err in results
            if err is None and out.status in ('credited', 'completed_purchase')
        ]
        self.assertEqual(len(credited), 1, results)
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.user, transaction_type=TT.VIP_REWARD, status=WalletTransaction.Status.COMPLETED,
            ).count(),
            1,
        )
        self.assertEqual(VIPReward.objects.filter(vip_purchase=self.purchase).count(), 1)
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.withdrawable_balance, Decimal('3.75000000'))

    def test_repeated_command_runs_are_idempotent(self) -> None:
        """§53/§55 — full batch twice: wallet credits exactly once."""
        call_command('process_vip_rewards', '--cycle-date', self.cycle.isoformat(), stdout=None)
        call_command('process_vip_rewards', '--cycle-date', self.cycle.isoformat(), stdout=None)
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.user, transaction_type=TT.VIP_REWARD, status=WalletTransaction.Status.COMPLETED,
            ).count(),
            1,
        )
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.withdrawable_balance, Decimal('3.75000000'))
