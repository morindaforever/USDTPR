"""VIP system tests (Section 7): plans, purchase, wallet/ledger integration,
idempotency, welcome-claim guard, isolation, and concurrency."""

from decimal import Decimal
from threading import Barrier, Thread

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.vip.models import VIPPlan, VIPPurchase
from apps.vip.services import VIPError, plan_purchase_summary, purchase_plan
from apps.wallet.models import Wallet, WalletTransaction
from apps.wallet.services import credit

TT = WalletTransaction.TransactionType
D = WalletTransaction.Direction


class VIPTestBase(TestCase):
    """Base with a funded user, a second user, and plan fixtures."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', stdout=None, verbosity=0)
        cls.plan1 = VIPPlan.objects.get(name='VIP 1')
        cls.plan2 = VIPPlan.objects.get(name='VIP 2')
        cls.welcome = VIPPlan.objects.get(plan_number=0)

    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='vip@example.com', password='S3curePass!', phone='+15550300001', full_name='VIP User'
        )
        self.other = User.objects.create_user(
            email='vipother@example.com', password='S3curePass!', phone='+15550300002', full_name='Other'
        )
        Wallet.objects.create(user=self.user)
        Wallet.objects.create(user=self.other)
        self.fund_user()

    def fund_user(self, amount: str = '100') -> None:
        credit(
            user=self.user, amount=amount, balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
            transaction_type=TT.ADJUSTMENT, idempotency_key=f'seed-{self.user.pk}-{amount}',
        )

    def wallet(self) -> Wallet:
        return Wallet.objects.get(user=self.user)

    def refresh(self) -> None:
        self.wallet().refresh_from_db()

    def buy(self, plan, key: str, user=None) -> VIPPurchase:
        return purchase_plan(
            user=user or self.user, plan_id=plan.pk, idempotency_key=key,
        ).purchase


class PlanEndpointTests(VIPTestBase):
    def test_plan_list_public(self) -> None:
        res = self.client.get(reverse('vip:plans'))
        self.assertEqual(res.status_code, 200)
        names = [row['name'] for row in res.json()['data']]
        self.assertIn('VIP 1', names)
        self.assertNotIn('Hidden Plan', names)

    def test_inactive_plan_hidden(self) -> None:
        self.plan2.is_active = False
        self.plan2.save()
        names = [row['name'] for row in self.client.get(reverse('vip:plans')).json()['data']]
        self.assertNotIn('VIP 2', names)
        self.plan2.is_active = True
        self.plan2.save()

    def test_plan_detail_and_404(self) -> None:
        res = self.client.get(reverse('vip:plan-detail', args=[self.plan1.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['data']['name'], 'VIP 1')
        self.assertEqual(
            self.client.get(reverse('vip:plan-detail', args=[99999])).status_code, 404,
        )

    def test_decimal_strings_in_payload(self) -> None:
        data = self.client.get(reverse('vip:plan-detail', args=[self.plan1.pk])).json()['data']
        self.assertIsInstance(data['investment_amount'], str)
        self.assertEqual(Decimal(data['investment_amount']), Decimal('10.00000000'))
        self.assertEqual(data['daily_rate_percent'], '25.00')


class PurchaseEndpointTests(VIPTestBase):
    def purchase(self, plan_id=1, key='k-1', token_user=None):
        return self.client.post(
            reverse('vip:purchase'),
            data={'plan_id': plan_id, 'idempotency_key': key},
            content_type='application/json',
            **self._auth(token_user or self.user),
        )

    def _auth(self, user):
        from rest_framework_simplejwt.tokens import RefreshToken
        return {'HTTP_AUTHORIZATION': f'Bearer {RefreshToken.for_user(user).access_token}'}

    def test_purchase_success_accounting(self) -> None:
        res = self.purchase(plan_id=self.plan1.pk, key='buy-1')
        self.assertEqual(res.status_code, 201)
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('90.00000000'))
        self.assertEqual(self.wallet().total_balance, Decimal('90.00000000'))
        ledger = WalletTransaction.objects.filter(
            user=self.user, transaction_type=TT.VIP_PURCHASE, idempotency_key__endswith='buy-1',
        )
        self.assertEqual(ledger.count(), 1)
        row = ledger.get()
        self.assertEqual(row.direction, D.DEBIT)
        self.assertEqual(row.status, WalletTransaction.Status.COMPLETED)
        purchase = VIPPurchase.objects.get(user=self.user, idempotency_key='buy-1')
        self.assertEqual(purchase.status, VIPPurchase.Status.ACTIVE)

    def test_snapshot_survives_plan_edit(self) -> None:
        self.purchase(plan_id=self.plan1.pk, key='snap-1')
        self.plan1.investment_amount = Decimal('99')
        self.plan1.target_amount = Decimal('150')
        self.plan1.save()
        purchase = VIPPurchase.objects.get(user=self.user, idempotency_key='snap-1')
        self.assertEqual(purchase.investment_amount, Decimal('10.00000000'))
        self.assertEqual(purchase.target_amount, Decimal('15.00000000'))
        self.assertEqual(purchase.daily_rate_snapshot, self.plan1.daily_rate)

    def test_insufficient_balance(self) -> None:
        Wallet.objects.filter(user=self.user).update(withdrawable_balance=Decimal('5'))
        res = self.purchase(plan_id=self.plan1.pk, key='poor-1')
        self.assertEqual(res.status_code, 400)
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('5'))
        self.assertFalse(VIPPurchase.objects.filter(user=self.user).exists())
        self.assertFalse(
            WalletTransaction.objects.filter(
                user=self.user,
                transaction_type=TT.VIP_PURCHASE,
                status=WalletTransaction.Status.COMPLETED,
            ).exists()
        )

    def test_inactive_and_invalid_plan(self) -> None:
        self.plan1.is_active = False
        self.plan1.save()
        try:
            purchase_plan(user=self.user, plan_id=self.plan1.pk, idempotency_key='off-1')
            self.fail('expected VIPError')
        except VIPError:
            pass
        self.plan1.is_active = True
        self.plan1.save()
        with self.assertRaises(VIPError):
            purchase_plan(user=self.user, plan_id=99999, idempotency_key='nope-1')

    def test_frontend_cannot_set_amounts(self) -> None:
        res = self.client.post(
            reverse('vip:purchase'),
            data={
                'plan_id': self.plan1.pk,
                'idempotency_key': 'cheat-1',
                'amount': '0.00000001',
                'target_amount': '99999',
                'daily_rate': '99',
            },
            content_type='application/json',
            **self._auth(self.user),
        )
        self.assertEqual(res.status_code, 201)
        purchase = VIPPurchase.objects.get(user=self.user, idempotency_key='cheat-1')
        self.assertEqual(purchase.investment_amount, Decimal('10.00000000'))
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('90.00000000'))

    def test_idempotent_replay(self) -> None:
        first = self.purchase(plan_id=self.plan1.pk, key='replay-1')
        again = self.purchase(plan_id=self.plan1.pk, key='replay-1')
        self.assertEqual(first.status_code, 201)
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()['data']['already_existed'])
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('90.00000000'))
        self.assertEqual(VIPPurchase.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.user, transaction_type=TT.VIP_PURCHASE,
            ).count(), 1,
        )

    def test_missing_idempotency_key_rejected(self) -> None:
        res = self.purchase(plan_id=self.plan1.pk, key='')
        self.assertEqual(res.status_code, 400)

    def test_suspended_user_cannot_purchase(self) -> None:
        self.user.account_status = User.AccountStatus.SUSPENDED
        self.user.save()
        with self.assertRaises(VIPError):
            purchase_plan(user=self.user, plan_id=self.plan1.pk, idempotency_key='susp-1')
        self.user.account_status = User.AccountStatus.ACTIVE
        self.user.save()

    def test_banned_user_cannot_purchase(self) -> None:
        self.user.account_status = User.AccountStatus.BANNED
        self.user.save()
        with self.assertRaises(VIPError):
            purchase_plan(user=self.user, plan_id=self.plan1.pk, idempotency_key='ban-1')
        self.user.account_status = User.AccountStatus.ACTIVE
        self.user.save()

    def test_unauthenticated_purchase_401(self) -> None:
        self.client.logout()
        res = self.client.post(
            reverse('vip:purchase'),
            data={'plan_id': self.plan1.pk, 'idempotency_key': 'anon-1'},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 401)

    def test_audit_notification_ledger_created(self) -> None:
        self.purchase(plan_id=self.plan1.pk, key='audit-1')
        purchase = VIPPurchase.objects.get(user=self.user, idempotency_key='audit-1')
        self.assertTrue(AuditLog.objects.filter(target_id=purchase.purchase_id).exists())
        self.assertTrue(
            Notification.objects.filter(user=self.user, notification_type=Notification.NotificationType.VIP).exists()
        )

    def test_history_and_active_isolated(self) -> None:
        purchase = self.buy(self.plan1, 'iso-1')
        res = self.client.get(reverse('vip:active'), **self._auth(self.user))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()['data']), 1)
        self.assertEqual(res.json()['data'][0]['purchase_id'], purchase.purchase_id)
        # Other user sees nothing of user's purchases.
        res_b = self.client.get(reverse('vip:active'), **self._auth(self.other))
        self.assertEqual(res_b.json()['data'], [])

    def test_user_cannot_touch_other_users_purchase(self) -> None:
        purchase = self.buy(self.plan1, 'own-1')
        res = self.client.get(
            reverse('vip:purchases'), **self._auth(self.other),
        )
        ids = [row['purchase_id'] for row in res.json()['data']]
        self.assertNotIn(purchase.purchase_id, ids)


class DepositBucketPurchaseTests(VIPTestBase):
    """Purchases spend the deposit bucket first, then withdrawable.

    Approved deposits credit DEPOSIT balance; a plan bought right after a
    deposit must work with no manual conversion step.
    """

    def test_purchase_spends_deposit_balance_first(self) -> None:
        credit(
            user=self.user, amount='50', balance_type=WalletTransaction.BalanceType.DEPOSIT,
            transaction_type=TT.DEPOSIT, reference_type='deposit', idempotency_key='depbuy-seed-1',
        )
        purchase = self.buy(self.plan1, 'dep-buy-1')  # VIP 1 = 10 USDT
        self.assertEqual(purchase.status, VIPPurchase.Status.ACTIVE)
        self.refresh()
        self.assertEqual(self.wallet().deposit_balance, Decimal('40.00000000'))
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('100.00000000'))
        self.assertEqual(self.wallet().total_balance, Decimal('140.00000000'))

    def test_purchase_falls_back_across_buckets(self) -> None:
        credit(
            user=self.user, amount='4', balance_type=WalletTransaction.BalanceType.DEPOSIT,
            transaction_type=TT.DEPOSIT, reference_type='deposit', idempotency_key='depbuy-seed-2',
        )
        purchase = self.buy(self.plan1, 'dep-buy-2')  # 10 = 4 deposit + 6 withdrawable
        self.assertEqual(purchase.status, VIPPurchase.Status.ACTIVE)
        self.refresh()
        self.assertEqual(self.wallet().deposit_balance, Decimal('0.00000000'))
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('94.00000000'))
        rows = WalletTransaction.objects.filter(
            user=self.user, transaction_type=TT.VIP_PURCHASE,
        ).order_by('balance_type')
        self.assertEqual(rows.count(), 2)
        self.assertEqual(rows.get(balance_type=WalletTransaction.BalanceType.DEPOSIT).amount, Decimal('4.00000000'))
        self.assertEqual(rows.get(balance_type=WalletTransaction.BalanceType.WITHDRAWABLE).amount, Decimal('6.00000000'))

    def test_purchase_rejected_when_combined_is_short(self) -> None:
        Wallet.objects.filter(user=self.user).update(withdrawable_balance=Decimal('5'), total_balance=Decimal('5'))
        with self.assertRaises(VIPError):
            self.buy(self.plan1, 'dep-buy-3')
        self.assertFalse(VIPPurchase.objects.filter(user=self.user, idempotency_key='dep-buy-3').exists())

    def test_summary_uses_combined_balance(self) -> None:
        credit(
            user=self.user, amount='50', balance_type=WalletTransaction.BalanceType.DEPOSIT,
            transaction_type=TT.DEPOSIT, reference_type='deposit', idempotency_key='depbuy-seed-4',
        )
        summary = plan_purchase_summary(self.user, self.plan1)
        self.assertEqual(summary['available_balance'], Decimal('150.00000000'))
        self.assertTrue(summary['sufficient'])


class VIPConcurrencyBase(TransactionTestCase):
    """Real-thread tests need TransactionTestCase: TestCase wraps the main
    thread in an uncommitted transaction that worker threads cannot see and
    would deadlock against on the wallet row lock."""

    def setUp(self) -> None:
        # TransactionTestCase truncates tables between tests, so (re)seed.
        call_command('seed_demo_data', stdout=None, verbosity=0)
        self.plan1 = VIPPlan.objects.get(name='VIP 1')
        self.welcome = VIPPlan.objects.get(plan_number=0)
        self.user = User.objects.create_user(
            email='vipconc@example.com', password='S3curePass!', phone='+15550300011', full_name='VIP Conc'
        )
        Wallet.objects.create(user=self.user)

    def _run_parallel(self, fn, workers: int):
        from concurrent.futures import ThreadPoolExecutor
        barrier = Barrier(workers)

        def runner(index: int):
            try:
                barrier.wait()
                return fn(index), None
            except Exception as exc:  # noqa: BLE001 - outcome collected below
                return None, exc
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(runner, range(workers)))


class WelcomePlanTests(VIPTestBase):
    def test_first_claim_ok_second_rejected(self) -> None:
        first = self.buy(self.welcome, 'WELCOME_CLAIM_x1')
        self.assertEqual(first.status, VIPPurchase.Status.ACTIVE)
        with self.assertRaises(VIPError):
            self.buy(self.welcome, 'WELCOME_CLAIM_x2')
        self.assertEqual(VIPPurchase.objects.filter(user=self.user, vip_plan=self.welcome).count(), 1)

    def test_different_key_same_claim_rejected(self) -> None:
        self.buy(self.welcome, 'WELCOME_CLAIM_a')
        with self.assertRaises(VIPError):
            self.buy(self.welcome, 'totally-different-key')

class ConcurrencyTests(VIPConcurrencyBase):
    def test_parallel_purchases_cannot_double_spend(self) -> None:
        """15 USDT; two VIP 1 (10) requests → exactly one must succeed."""
        Wallet.objects.filter(user=self.user).update(withdrawable_balance=Decimal('15'), total_balance=Decimal('15'))

        def attempt(index: int):
            purchase_plan(user=self.user, plan_id=self.plan1.pk, idempotency_key=f'race-{index}')
            return 'ok'

        results = self._run_parallel(attempt, workers=2)
        ok = [r for r, err in results if err is None]
        self.assertEqual(len(ok), 1, results)
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.withdrawable_balance, Decimal('5.00000000'))
        self.assertEqual(
            WalletTransaction.objects.filter(
                user=self.user, transaction_type=TT.VIP_PURCHASE,
                status=WalletTransaction.Status.COMPLETED,
            ).count(), 1,
        )

    def test_concurrent_welcome_claims(self) -> None:
        """Two threads claiming the free plan at once → exactly one wins."""

        def attempt(index: int):
            purchase_plan(user=self.user, plan_id=self.welcome.pk, idempotency_key=f'WELCOME_CLAIM_t{index}')
            return 'ok'

        results = self._run_parallel(attempt, workers=2)
        ok = [r for r, err in results if err is None]
        self.assertEqual(len(ok), 1, results)
        self.assertEqual(VIPPurchase.objects.filter(user=self.user, vip_plan=self.welcome).count(), 1)


class AccountingInvariantTests(VIPTestBase):
    def test_welcome_claim_is_free_and_guarded(self) -> None:
        """WELCOME invests 0 → no debit, no ledger row; second claim blocked."""
        purchase = self.buy(self.welcome, 'WELCOME_CLAIM_free1')
        self.assertEqual(purchase.status, VIPPurchase.Status.ACTIVE)
        self.refresh()
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('100.00000000'))
        self.assertFalse(
            WalletTransaction.objects.filter(user=self.user, transaction_type=TT.VIP_PURCHASE).exists()
        )
        with self.assertRaises(VIPError):
            self.buy(self.welcome, 'WELCOME_CLAIM_free2')

    def test_no_orphan_rows_on_debit_failure(self) -> None:
        """Overdraft → VIPError, and the pre-created purchase row rolls back."""
        Wallet.objects.filter(user=self.user).update(withdrawable_balance=Decimal('0'), total_balance=Decimal('0'))
        with self.assertRaises(VIPError):
            self.buy(self.plan1, 'orphan-check')
        self.assertFalse(VIPPurchase.objects.filter(user=self.user, idempotency_key='orphan-check').exists())
        self.assertFalse(
            WalletTransaction.objects.filter(user=self.user, transaction_type=TT.VIP_PURCHASE).exists()
        )
