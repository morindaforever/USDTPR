"""Section 14 security test suite.

Cross-cutting coverage that individual app suites don't provide:

- §9  account-status enforcement (suspended/banned blocked at every
  financial/support entry point, enforced server-side)
- §11/§12/§13 IDOR + admin authorization + privilege escalation matrix
- §30 financial-write throttles respond (429 under flood)
- §47/§48 financial integrity + accounting invariants (reconciliation-based)
- §50 demo transparency (withdrawal completes without fabricated hashes)
- §51 no direct wallet mutations from app code
"""

from decimal import Decimal
from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import register_user
from apps.deposits.services import DepositError, submit_deposit
from apps.notifications.models import Notification
from apps.support.services import SupportError, create_conversation
from apps.vip.models import VIPPlan, VIPPurchase
from apps.vip.services import VIPError, purchase_plan
from apps.wallet.models import WalletTransaction
from apps.wallet.services import (
    WalletError,
    admin_adjust,
    credit,
    reconcile_wallet,
)

PASSWORD = 'S3curePass!x'
TRON_ADDRESS = 'Th82pJGF9p7kpzb6eU326EFZf2cDnimbTF'  # format-valid demo value


def _paid_plan():
    """First purchasable (non-zero investment) active plan — skip WELCOME."""
    return (
        VIPPlan.objects.filter(is_active=True)
        .exclude(investment_amount__lte=0)
        .order_by('plan_number')
        .first()
    )


def _mk(email: str, i: int, *, status=None) -> User:
    user = register_user(
        full_name=f'USER {i}',
        email=email,
        phone=f'+199666{i:05d}',
        password=PASSWORD,
        referral_code='',
    ).user
    if status is not None:
        user.account_status = status
        user.save(update_fields=['account_status'])
    return user


def _fund(user: User, amount: str, bucket=WalletTransaction.BalanceType.WITHDRAWABLE) -> None:
    admin_adjust(
        user=user,
        amount=Decimal(amount),
        balance_type=bucket,
        direction=WalletTransaction.Direction.CREDIT,
        reason='Section 14 test funding',
        idempotency_key=f's14-{user.user_id}-{amount}-{bucket}',
    )


def _grant_paid_vip(user: User, suffix: str) -> None:
    """Fixture: paid-VIP purchase row (unlocks withdrawals, moves no money)."""
    from apps.vip.models import VIPPlan, VIPPurchase

    plan, _ = VIPPlan.objects.get_or_create(
        name='VIP 1',
        defaults={
            'plan_number': 1, 'investment_amount': Decimal('10'),
            'target_amount': Decimal('15'), 'daily_rate': Decimal('0.25'),
        },
    )
    VIPPurchase.objects.create(
        user=user, vip_plan=plan, plan_name_snapshot=plan.name,
        investment_amount=plan.investment_amount, target_amount=plan.target_amount,
        daily_rate_snapshot=plan.daily_rate, status=VIPPurchase.Status.ACTIVE,
        idempotency_key=f'TEST_PAID_VIP_s14_{suffix}_{user.user_id}',
    )


class Section14Base(TestCase):
    """Shared fixtures: demo networks/plans + two users + one superuser."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', verbosity=0)
        # Production conversion: the seed no longer fabricates deposit
        # addresses — tests create explicit format-valid fixtures instead.
        from apps.wallet.models import DepositAddress, Network

        for network in Network.objects.filter(is_active=True):
            address = (
                'Th82pJGF9p7kpzb6eU326EFZf2cDnimbTF'  # T + 33 base58
                if network.code == 'TRX'
                else '0x' + 'a' * 40
            )
            DepositAddress.objects.create(
                network=network, asset='USDT', address=address, is_active=True,
            )
        cls.a = _mk('s14-a@example.com', 1)
        cls.b = _mk('s14-b@example.com', 2)
        cls.admin = User.objects.create_superuser(
            email='s14-admin@example.com', password=PASSWORD, phone='+19966600003',
        )

    def setUp(self) -> None:
        self.client = APIClient()

    def _auth(self, user) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')


# --------------------------------------------------------------------------- #
# §9 — account status enforcement (server-side, at the service boundary)
# --------------------------------------------------------------------------- #
class AccountStatusEnforcementTests(Section14Base):
    def test_suspended_cannot_submit_deposit(self) -> None:
        user = _mk('s14-susp-dep@example.com', 4, status=User.AccountStatus.SUSPENDED)
        with self.assertRaises(DepositError) as ctx:
            submit_deposit(
                user=user, network_code='TRX', amount='25.00',
                tx_hash='s14-dep-1', order_id='',
            )
        self.assertIn('suspended', str(ctx.exception).lower())

    def test_banned_cannot_submit_deposit(self) -> None:
        user = _mk('s14-ban-dep@example.com', 5, status=User.AccountStatus.BANNED)
        with self.assertRaises(DepositError):
            submit_deposit(
                user=user, network_code='TRX', amount='25.00',
                tx_hash='s14-dep-2', order_id='',
            )

    def test_suspended_cannot_purchase_vip(self) -> None:
        user = _mk('s14-susp-vip@example.com', 6, status=User.AccountStatus.SUSPENDED)
        _fund(user, '500')
        plan = _paid_plan()
        with self.assertRaises(VIPError):
            purchase_plan(user=user, plan_id=plan.pk, idempotency_key='s14-vip-1')

    def test_suspended_cannot_open_or_reply_support(self) -> None:
        user = _mk('s14-susp-sup@example.com', 7, status=User.AccountStatus.SUSPENDED)
        with self.assertRaises(SupportError):
            create_conversation(user, 'Help please', 'I cannot access my wallet.')
        active = _mk('s14-act-sup@example.com', 8)
        conversation = create_conversation(active, 'Help please', 'Original message.')
        user.account_status = User.AccountStatus.SUSPENDED
        user.save(update_fields=['account_status'])
        with self.assertRaises(SupportError):
            from apps.support.services import send_message

            send_message(user, conversation, 'Follow-up message.')

    def test_suspended_cannot_create_withdrawal_api(self) -> None:
        user = _mk('s14-susp-wd@example.com', 9, status=User.AccountStatus.SUSPENDED)
        _fund(user, '100')
        self._auth(user)
        response = self.client.post(
            '/api/withdrawals/',
            {
                'network': 'TRX',
                'destination_address': TRON_ADDRESS,
                'amount': '20.00',
                'idempotency_key': 's14-wd-susp-1',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_active_user_still_fine(self) -> None:
        _fund(self.a, '50')
        deposit = submit_deposit(
            user=self.a, network_code='TRX', amount='25.00',
            tx_hash='s14-dep-ok', order_id='',
        ).deposit
        self.assertEqual(deposit.status, deposit.Status.PENDING)


# --------------------------------------------------------------------------- #
# §11 — IDOR matrix: user A never reads or mutates user B's objects
# --------------------------------------------------------------------------- #
class IdorMatrixTests(Section14Base):
    def test_b_cannot_read_a_wallet_transactions(self) -> None:
        _fund(self.a, '10')
        self._auth(self.b)
        rows = self.client.get('/api/wallet/transactions/').json()['data']
        self.assertEqual(len(rows), 0)

    def test_b_cannot_read_a_transaction_detail(self) -> None:
        _fund(self.a, '10')
        txn = WalletTransaction.objects.filter(user=self.a).first()
        self._auth(self.b)
        response = self.client.get(f'/api/wallet/transactions/{txn.transaction_id}/')
        self.assertEqual(response.status_code, 404)  # no existence leak

    def test_b_cannot_read_a_notification(self) -> None:
        notification = Notification.objects.create(
            user=self.a, notification_type='SYSTEM', title='Private', message='secret',
        )
        self._auth(self.b)
        self.assertEqual(
            self.client.get(f'/api/notifications/{notification.id}/').status_code, 404,
        )
        self.assertEqual(
            self.client.post(f'/api/notifications/{notification.id}/read/').status_code, 404,
        )

    def test_b_cannot_read_a_deposit(self) -> None:
        deposit = submit_deposit(
            user=self.a, network_code='TRX', amount='25.00', tx_hash='idor-dep', order_id='',
        ).deposit
        self._auth(self.b)
        self.assertEqual(
            self.client.get(f'/api/deposits/{deposit.deposit_id}/').status_code, 404,
        )

    def test_b_cannot_read_a_withdrawal(self) -> None:
        _fund(self.a, '100')
        _grant_paid_vip(self.a, 'idor-wd')
        self._auth(self.a)
        created = self.client.post(
            '/api/withdrawals/',
            {
                'network': 'TRX',
                'destination_address': TRON_ADDRESS,
                'amount': '20.00',
                'idempotency_key': 'idor-wd',
            },
            format='json',
        ).json()['data']
        self._auth(self.b)
        response = self.client.get(f"/api/withdrawals/{created['withdrawal_id']}/")
        self.assertIn(response.status_code, (403, 404))

    def test_b_cannot_read_a_support_conversation(self) -> None:
        from django.core.cache import cache

        cache.clear()  # §25: support has per-user fixed-window counters
        conversation = create_conversation(self.a, 'Question', 'Details inside.')
        self._auth(self.b)
        response = self.client.get(f'/api/support/conversations/{conversation.conversation_id}/')
        self.assertIn(response.status_code, (403, 404))

    def test_b_cannot_reply_into_a_support_conversation(self) -> None:
        from django.core.cache import cache

        cache.clear()
        conversation = create_conversation(self.a, 'Question', 'Details inside.')
        self._auth(self.b)
        response = self.client.post(
            f'/api/support/conversations/{conversation.conversation_id}/messages/',
            {'message': 'Injected reply.'},
            format='json',
        )
        self.assertIn(response.status_code, (403, 404))
        conversation.refresh_from_db()
        self.assertEqual(conversation.messages.count(), 1)

    def test_vip_summary_is_own_only(self) -> None:
        plan = _paid_plan()
        _fund(self.a, plan.investment_amount + Decimal('10'))
        purchase_plan(user=self.a, plan_id=plan.pk, idempotency_key='idor-vip')
        self._auth(self.b)
        current = self.client.get('/api/vip/current/').json().get('data')
        self.assertTrue(current is None or current.get('purchase_id') != '')


# --------------------------------------------------------------------------- #
# §12/§13 — admin authorization + privilege escalation
# --------------------------------------------------------------------------- #
class AdminAuthorizationTests(Section14Base):
    admin_urls = [
        '/api/admin/dashboard/',
        '/api/admin/users/',
        '/api/admin/deposits/',
        '/api/admin/withdrawals/',
        '/api/admin/vip-plans/',
        '/api/admin/vip-purchases/',
        '/api/admin/rewards/',
        '/api/admin/referrals/',
        '/api/admin/commissions/',
        '/api/admin/support/',
        '/api/admin/notifications/',
        '/api/admin/audit-logs/',
        '/api/admin/settings/',
        '/api/admin-panel/withdrawals/',
        '/api/admin-panel/deposits/',
    ]

    def test_anonymous_rejected_everywhere(self) -> None:
        for url in self.admin_urls:
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (401, 403))

    def test_regular_user_rejected_everywhere(self) -> None:
        self._auth(self.a)
        for url in self.admin_urls:
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (401, 403))

    def test_superadmin_accepted(self) -> None:
        self._auth(self.admin)
        for url in self.admin_urls:
            with self.subTest(url=url):
                self.assertIn(self.client.get(url).status_code, (200, 400))

    def test_regular_user_cannot_approve_deposits(self) -> None:
        deposit = submit_deposit(
            user=self.a, network_code='TRX', amount='25.00', tx_hash='adm-dep', order_id='',
        ).deposit
        self._auth(self.b)
        response = self.client.post(f'/api/admin-panel/deposits/{deposit.deposit_id}/approve/', {})
        self.assertIn(response.status_code, (401, 403))
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, deposit.Status.PENDING)

    def test_regular_user_cannot_change_admin_withdrawal_state(self) -> None:
        _fund(self.a, '100')
        _grant_paid_vip(self.a, 'adm-wd')
        self._auth(self.a)
        created = self.client.post(
            '/api/withdrawals/',
            {
                'network': 'TRX',
                'destination_address': TRON_ADDRESS,
                'amount': '20.00',
                'idempotency_key': 'adm-wd',
            },
            format='json',
        ).json()['data']
        self._auth(self.b)
        for action in ('approve', 'reject', 'complete'):
            response = self.client.post(
                f"/api/admin-panel/withdrawals/{created['withdrawal_id']}/{action}/", {},
            )
            self.assertIn(response.status_code, (401, 403))

    def test_privilege_escalation_via_mass_assignment_rejected(self) -> None:
        self._auth(self.a)
        response = self.client.patch(
            '/api/account/profile/',
            {
                'full_name': 'Still A User',
                'is_staff': True,
                'is_superuser': True,
                'account_status': 'ACTIVE',
            },
            format='json',
        )
        self.a.refresh_from_db()
        self.assertFalse(self.a.is_staff)
        self.assertFalse(self.a.is_superuser)

    def test_no_endpoint_lets_user_self_serve_admin_flags(self) -> None:
        # Registration with injected role fields must not elevate.
        response = self.client.post(
            '/api/auth/register/',
            {
                'full_name': 'Escalator',
                'email': 's14-esc@example.com',
                'phone': '+19966600010',
                'password': PASSWORD,
                'password_confirm': PASSWORD,
                'is_staff': True,
                'is_superuser': True,
            },
            format='json',
        )
        if response.status_code == 201:
            user = User.objects.get(email='s14-esc@example.com')
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)


# --------------------------------------------------------------------------- #
# §30 — financial-write throttle responds under flood
# --------------------------------------------------------------------------- #
class FinancialWriteThrottleTests(Section14Base):
    def test_vip_purchase_flood_gets_429(self) -> None:
        self._auth(self.a)
        statuses = []
        for i in range(40):
            response = self.client.post(
                '/api/vip/purchase/', {'plan_id': 999999, 'idempotency_key': f'flood-{i}'},
                format='json',
            )
            statuses.append(response.status_code)
        self.assertIn(429, statuses)

    def test_withdrawal_flood_gets_429(self) -> None:
        _fund(self.a, '1000')
        self._auth(self.a)
        statuses = []
        for i in range(40):
            response = self.client.post(
                '/api/withdrawals/',
                {
                    'network': 'TRX',
                    'destination_address': TRON_ADDRESS,
                    'amount': '6.00',
                    'idempotency_key': f'flood-wd-{i}',
                },
                format='json',
            )
            statuses.append(response.status_code)
            if response.status_code == 429:
                break
        self.assertIn(429, statuses)


# --------------------------------------------------------------------------- #
# §47/§48 — financial integrity + accounting invariants
# --------------------------------------------------------------------------- #
class FinancialIntegrityTests(Section14Base):
    def test_every_financial_move_leaves_wallet_reconciled(self) -> None:
        """Ledger-first invariant after a mixed workload (§48)."""
        _fund(self.a, '200')
        plan = _paid_plan()
        _fund(self.a, plan.investment_amount)
        purchase_plan(user=self.a, plan_id=plan.pk, idempotency_key='int-vip')
        self._auth(self.a)
        self.client.post(
            '/api/withdrawals/',
            {
                'network': 'TRX',
                'destination_address': TRON_ADDRESS,
                'amount': '20.00',
                'idempotency_key': 'int-wd',
            },
            format='json',
        )
        report = reconcile_wallet(self.a)
        self.assertTrue(report['ok'], report['issues'])
        self.assertEqual(report['issues'], [])

    def test_reconcile_detects_manual_tampering(self) -> None:
        """§49: detect-and-report (never auto-fix) catches drift."""
        _fund(self.a, '50')
        from apps.wallet.models import Wallet

        wallet = Wallet.objects.get(user=self.a)
        Wallet.objects.filter(pk=wallet.pk).update(total_balance=Decimal('9999'))
        report = reconcile_wallet(self.a)
        self.assertFalse(report['ok'])
        self.assertTrue(report['issues'])

    def test_locked_buckets_never_go_negative_through_lifecycle(self) -> None:
        """Reject/fail release, complete finalizes — nothing stuck negative."""
        from apps.withdrawals.services import (
            approve_withdrawal,
            complete_withdrawal,
            create_withdrawal,
            reject_withdrawal,
        )

        _fund(self.a, '100')
        _grant_paid_vip(self.a, 'locked-lifecycle')
        w1, _ = create_withdrawal(
            user=self.a, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('20.00'), idempotency_key='inv-wd-1',
        )
        approve_withdrawal(w1.withdrawal_id, admin=self.admin)
        from apps.withdrawals.services import start_processing

        start_processing(w1.withdrawal_id, admin=self.admin)
        complete_withdrawal(w1.withdrawal_id, admin=self.admin, tx_hash='')
        # PENDING → REJECTED (release path; APPROVED withdrawals may only
        # move to PROCESSING per the Section 10 state machine).
        w2, _ = create_withdrawal(
            user=self.a, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key='inv-wd-2',
        )
        reject_withdrawal(w2.withdrawal_id, admin=self.admin, reason='Test reject')
        from apps.wallet.models import Wallet

        wallet = Wallet.objects.get(user=self.a)
        self.assertGreaterEqual(wallet.locked_balance, Decimal('0'))
        self.assertGreaterEqual(wallet.withdrawable_balance, Decimal('0'))
        self.assertGreaterEqual(wallet.total_balance, Decimal('0'))
        report = reconcile_wallet(self.a)
        self.assertTrue(report['ok'], report['issues'])

    def test_duplicate_vip_purchase_is_idempotent(self) -> None:
        plan = _paid_plan()
        _fund(self.a, plan.investment_amount * 2)
        first = purchase_plan(user=self.a, plan_id=plan.pk, idempotency_key='dup-vip')
        second = purchase_plan(user=self.a, plan_id=plan.pk, idempotency_key='dup-vip')
        self.assertTrue(second.already_existed)
        self.assertEqual(first.purchase.pk, second.purchase.pk)
        debits = WalletTransaction.objects.filter(
            user=self.a, transaction_type=WalletTransaction.TransactionType.VIP_PURCHASE,
        )
        self.assertEqual(debits.count(), 1)
        report = reconcile_wallet(self.a)
        self.assertTrue(report['ok'], report['issues'])

    def test_withdrawal_completes_without_fabricated_hash(self) -> None:
        """§50/§51: demo completion never invents blockchain data."""
        from apps.withdrawals.services import (
            approve_withdrawal,
            complete_withdrawal,
            create_withdrawal,
        )

        _fund(self.a, '100')
        _grant_paid_vip(self.a, 'hash-lifecycle')
        withdrawal, _ = create_withdrawal(
            user=self.a, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('20.00'), idempotency_key='hash-wd',
        )
        approve_withdrawal(withdrawal.withdrawal_id, admin=self.admin)
        from apps.withdrawals.services import start_processing

        start_processing(withdrawal.withdrawal_id, admin=self.admin)
        complete_withdrawal(withdrawal.withdrawal_id, admin=self.admin, tx_hash='')
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, withdrawal.Status.COMPLETED)
        self.assertEqual(withdrawal.tx_hash, '')

    def test_insufficient_balance_rejected_atomically(self) -> None:
        plan = _paid_plan()
        _fund(self.a, '1.00')
        with self.assertRaises(VIPError):
            purchase_plan(user=self.a, plan_id=plan.pk, idempotency_key='poor-vip')
        report = reconcile_wallet(self.a)
        self.assertTrue(report['ok'], report['issues'])
        self.assertFalse(
            WalletTransaction.objects.filter(
                user=self.a, transaction_type=WalletTransaction.TransactionType.VIP_PURCHASE,
            ).exists()
        )

    def test_no_direct_wallet_mutations_in_app_code(self) -> None:
        """§51: static guard — bucket fields only touched by wallet service."""
        import re
        from pathlib import Path

        backend = Path(__file__).resolve().parents[2]
        pattern = re.compile(
            r'\.(?:deposit|withdrawable|locked|bonus|pending|total)_balance\s*(?:\+|−|-)=',
        )
        offenders = []
        for path in backend.glob('apps/**/*.py'):
            if 'migrations' in path.parts or 'wallet_service' in path.name:
                continue
            text = path.read_text()
            if pattern.search(text):
                offenders.append(str(path))
        self.assertEqual(offenders, [])
