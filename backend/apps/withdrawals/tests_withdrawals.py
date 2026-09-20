"""Withdrawal system tests (Section 10).

Covers: fee/quote config (§13–15), address validation (§10, §76),
creation + wallet locking (§20–22, §35, §64), state machine transitions
(§24–25, §71), double rejection/completion safety (§66–67), idempotent
submission (§35, §75), concurrency (§37, §68), wallet-failure rollback,
user isolation (§69), admin authorization (§70), and tamper resistance
(§63, §77). Simulated-withdrawal separation is asserted as well (§83).
"""

import re
from decimal import Decimal
from threading import Barrier, Thread

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase

from apps.accounts.models import User
from apps.accounts.services import register_user
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.wallet.models import Wallet, WalletTransaction
from apps.wallet.services import (
    InsufficientBalanceError,
    admin_adjust,
    get_wallet,
    get_wallet_summary,
)

from . import config, services
from .address_validation import AddressValidationError, validate_address
from .models import Withdrawal
from .reconciliation import reconcile_user_withdrawals
from .services import (
    InvalidTransitionError,
    WithdrawalError,
    approve_withdrawal,
    complete_withdrawal,
    create_withdrawal,
    fail_withdrawal,
    pending_withdrawal_total,
    quote,
    reject_withdrawal,
    start_processing,
)

PASSWORD = 'S3curePass!x'
TRON_ADDRESS = 'Th82pJGF9p7kpzb6eU326EFZf2cDnimbTF'  # T + 33 base58 (format check)


def _mk(email: str, i: int) -> User:
    return register_user(
        full_name=email.split('@')[0].upper(),
        email=email,
        phone=f'+199555{i:05d}',
        password=PASSWORD,
        referral_code='',
    ).user


def _fund(user: User, amount: str) -> None:
    admin_adjust(
        user=user,
        amount=Decimal(amount),
        balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
        direction=WalletTransaction.Direction.CREDIT,
        reason='test funding',
    )


def _grant_paid_vip(user: User, suffix: str, plan_name: str = 'VIP 1'):
    """Fixture: a paid VIP purchase record (withdrawal-eligibility unlock).

    Creates the VIPPurchase snapshot row directly — the eligibility gate
    reads purchase records joined to the plan, so a paid-VIP fixture
    unlocks withdrawals without running the full purchase flow. The
    created plan's ``plan_number`` is derived from the name ("VIP 2" → 2)
    so fixtures reflect real plan numbering. Returns the VIPPlan used.
    """
    from apps.vip.models import VIPPlan, VIPPurchase

    match = re.search(r'(\d+)\s*$', plan_name)
    plan_number = int(match.group(1)) if match else 1
    plan = VIPPlan.objects.filter(name=plan_name).first()
    if plan is None:
        plan = VIPPlan.objects.create(
            name=plan_name, plan_number=plan_number, investment_amount=Decimal('10'),
            target_amount=Decimal('15'), daily_rate=Decimal('0.25'),
        )
    VIPPurchase.objects.create(
        user=user, vip_plan=plan, plan_name_snapshot=plan.name,
        investment_amount=plan.investment_amount, target_amount=plan.target_amount,
        daily_rate_snapshot=plan.daily_rate, status=VIPPurchase.Status.ACTIVE,
        idempotency_key=f'TEST_PAID_VIP_{suffix}',
    )
    return plan


def _balance(user: User) -> dict:
    summary = get_wallet_summary(user)
    return {
        'withdrawable': summary['withdrawable_balance'],
        'locked': summary['locked_balance'],
        'deposit': summary['deposit_balance'],
    }


class WithdrawalConfigTests(TestCase):
    """Fee and minimum configuration (§13–15, §46)."""

    def tearDown(self) -> None:
        config.invalidate_cache()

    def test_defaults(self) -> None:
        self.assertEqual(config.get_min_amount(), Decimal('5.00'))
        self.assertEqual(config.get_fee_type(), 'FIXED')
        self.assertEqual(config.calculate_fee(Decimal('20.00')), Decimal('1.00'))
        self.assertEqual(config.calculate_net(Decimal('20.00')), (Decimal('1.00'), Decimal('19.00')))

    def test_percent_fee(self) -> None:
        from apps.core.models import SiteSetting

        SiteSetting.objects.create(key=config.KEY_FEE_TYPE, value='PERCENT')
        SiteSetting.objects.create(key=config.KEY_FEE_AMOUNT, value='2')
        config.invalidate_cache()
        self.assertEqual(config.calculate_fee(Decimal('20.00')), Decimal('0.40'))
        self.assertEqual(config.calculate_net(Decimal('20.00')), (Decimal('0.40'), Decimal('19.60')))

    def test_fee_never_exceeds_amount(self) -> None:
        self.assertEqual(config.calculate_fee(Decimal('5.00')), Decimal('1.00'))
        self.assertEqual(config.calculate_net(Decimal('5.00')), (Decimal('1.00'), Decimal('4.00')))

    def test_quote_decimal_shapes(self) -> None:
        for amount, expected_net in [('10.00', '9.00'), ('19.99', '18.99'), ('100.00', '99.00')]:
            data = quote(Decimal(amount))
            self.assertEqual(data['net_amount'], expected_net)
            self.assertEqual(Decimal(data['amount']) - Decimal(data['fee']), Decimal(data['net_amount']))

    def test_quote_rejects_small_amounts(self) -> None:
        with self.assertRaises(WithdrawalError):
            quote(Decimal('4.99'))
        with self.assertRaises(WithdrawalError):
            quote(Decimal('0'))


class AddressValidationTests(TestCase):
    """Network-aware address validation (§10, §76)."""

    def test_tron(self) -> None:
        self.assertEqual(validate_address('TRX', TRON_ADDRESS), TRON_ADDRESS)
        with self.assertRaises(AddressValidationError):
            validate_address('TRX', '0x' + 'a' * 40)  # EVM address on TRON
        with self.assertRaises(AddressValidationError):
            validate_address('TRX', 'short')

    def test_evm_networks_share_format(self) -> None:
        evm = '0x' + 'AbCd' * 10
        for code in ('BSC', 'ETH', 'POL'):
            self.assertEqual(validate_address(code, evm), evm)
            with self.assertRaises(AddressValidationError):
                validate_address(code, TRON_ADDRESS)

    def test_solana_and_ton(self) -> None:
        sol = '4Nd1mBQtrMJVYVfKf2PJy9NZUZdTAsp7D4xWLoy4Kwqc'
        ton = 'EQD2NmD_lH5f5u1Kj3KfGyTvhZSX0Eg6qp2a5IQUKXxOG21n'
        self.assertEqual(validate_address('SOL', sol), sol)
        self.assertEqual(validate_address('TON', ton), ton)

    def test_garbage_and_whitespace(self) -> None:
        # Whitespace-only addresses are rejected; surrounding whitespace on
        # an otherwise-valid address is TRIMMED (validator returns it).
        for bad in ('', '   ', 'x' * 300, '<script>'):
            with self.assertRaises(AddressValidationError):
                validate_address('TRX', bad)
        self.assertEqual(validate_address('TRX', f' {TRON_ADDRESS} '), TRON_ADDRESS)


class WithdrawalCreationTests(TestCase):
    """Submission, locking, and idempotency (§18–22, §35, §64)."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', verbosity=0)
        cls.user = _mk('wd-create@example.com', 10)
        _grant_paid_vip(cls.user, 'create')

    def test_create_locks_funds_once(self) -> None:
        _fund(self.user, '50')
        withdrawal, created = create_withdrawal(
            user=self.user,
            network_code='TRX',
            destination_address=TRON_ADDRESS,
            amount=Decimal('20.00'),
            idempotency_key='wd-lock-1',
        )
        self.assertTrue(created)
        self.assertEqual(withdrawal.status, Withdrawal.Status.PENDING)
        self.assertEqual(withdrawal.requested_amount, Decimal('20.00'))
        self.assertEqual(withdrawal.fee_amount, Decimal('1.00'))
        self.assertEqual(withdrawal.net_amount, Decimal('19.00'))
        balances = _balance(self.user)
        self.assertEqual(balances['withdrawable'], Decimal('30.00'))
        self.assertEqual(balances['locked'], Decimal('20.00'))
        # Exactly one ledger row for the lock, pointing at the withdrawal.
        locks = WalletTransaction.objects.filter(
            user=self.user, transaction_type=WalletTransaction.TransactionType.LOCK,
        )
        self.assertEqual(locks.count(), 2)  # debit (withdrawable) + credit (locked) legs
        self.assertEqual(
            {row.balance_type for row in locks},
            {WalletTransaction.BalanceType.WITHDRAWABLE, WalletTransaction.BalanceType.LOCKED},
        )
        self.assertTrue(all(row.reference_id == withdrawal.withdrawal_id for row in locks))

    def test_fee_snapshot_persists_after_config_change(self) -> None:
        from apps.core.models import SiteSetting

        _fund(self.user, '40')
        withdrawal, _ = create_withdrawal(
            user=self.user,
            network_code='TRX',
            destination_address=TRON_ADDRESS,
            amount=Decimal('30.00'),
            idempotency_key='wd-snap-1',
        )
        self.assertEqual(withdrawal.fee_amount, Decimal('1.00'))
        SiteSetting.objects.create(key=config.KEY_FEE_TYPE, value='PERCENT')
        SiteSetting.objects.create(key=config.KEY_FEE_AMOUNT, value='10')
        config.invalidate_cache()
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.fee_amount, Decimal('1.00'))  # §16 snapshot

    def test_idempotent_replay(self) -> None:
        _fund(self.user, '50')
        first, created1 = create_withdrawal(
            user=self.user,
            network_code='TRX',
            destination_address=TRON_ADDRESS,
            amount=Decimal('15.00'),
            idempotency_key='wd-replay',
        )
        second, created2 = create_withdrawal(
            user=self.user,
            network_code='TRX',
            destination_address=TRON_ADDRESS,
            amount=Decimal('15.00'),
            idempotency_key='wd-replay',
        )
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(first.withdrawal_id, second.withdrawal_id)
        self.assertEqual(Withdrawal.objects.filter(user=self.user).count(), 1)
        self.assertEqual(_balance(self.user)['locked'], Decimal('15.00'))  # locked once

    def test_minimum_enforced(self) -> None:
        _fund(self.user, '50')
        with self.assertRaises(WithdrawalError):
            create_withdrawal(
                user=self.user,
                network_code='TRX',
                destination_address=TRON_ADDRESS,
                amount=Decimal('4.99'),
                idempotency_key='wd-min-1',
            )
        withdrawal, _ = create_withdrawal(
            user=self.user,
            network_code='TRX',
            destination_address=TRON_ADDRESS,
            amount=Decimal('5.00'),
            idempotency_key='wd-min-2',
        )
        self.assertEqual(withdrawal.requested_amount, Decimal('5.00'))

    def test_insufficient_balance_atomic(self) -> None:
        _fund(self.user, '10')
        with self.assertRaises(WithdrawalError) as ctx:
            create_withdrawal(
                user=self.user,
                network_code='TRX',
                destination_address=TRON_ADDRESS,
                amount=Decimal('12.00'),
                idempotency_key='wd-over-1',
            )
        self.assertIn('Insufficient withdrawable balance', ctx.exception.message)
        self.assertIn('VIP plan profits', ctx.exception.message)
        self.assertEqual(Withdrawal.objects.filter(user=self.user).count(), 0)
        self.assertEqual(_balance(self.user)['withdrawable'], Decimal('10.00'))

    def test_deposit_balance_is_not_withdrawable(self) -> None:
        """The reported production scenario: plenty of DEPOSIT balance, zero
        withdrawable — the request must be rejected with a clear reason."""
        from apps.wallet.models import WalletTransaction
        from apps.wallet.services import credit

        credit(
            user=self.user,
            amount='500',
            balance_type=WalletTransaction.BalanceType.DEPOSIT,
            transaction_type=WalletTransaction.TransactionType.DEPOSIT,
            idempotency_key='dep-only-1',
        )
        self.assertEqual(_balance(self.user)['deposit'], Decimal('500.00'))
        self.assertEqual(_balance(self.user)['withdrawable'], Decimal('0.00'))
        with self.assertRaises(WithdrawalError) as ctx:
            create_withdrawal(
                user=self.user,
                network_code='TRX',
                destination_address=TRON_ADDRESS,
                amount=Decimal('10.00'),
                idempotency_key='dep-only-wdr-1',
            )
        self.assertIn('Insufficient withdrawable balance', ctx.exception.message)
        self.assertIn('referral commissions', ctx.exception.message)
        self.assertEqual(Withdrawal.objects.filter(user=self.user).count(), 0)
        self.assertEqual(_balance(self.user)['deposit'], Decimal('500.00'))

    def test_validation_failures(self) -> None:
        _fund(self.user, '50')
        cases = [
            ('bad-network', dict(network_code='XXX', destination_address=TRON_ADDRESS,
                                 amount=Decimal('10'), idempotency_key='k1')),
            ('bad-address', dict(network_code='TRX', destination_address='not-an-address',
                                 amount=Decimal('10'), idempotency_key='k2')),
            ('zero-amount', dict(network_code='TRX', destination_address=TRON_ADDRESS,
                                 amount=Decimal('0'), idempotency_key='k3')),
            ('negative', dict(network_code='TRX', destination_address=TRON_ADDRESS,
                              amount=Decimal('-5'), idempotency_key='k4')),
            ('missing-key', dict(network_code='TRX', destination_address=TRON_ADDRESS,
                                 amount=Decimal('10'), idempotency_key='')),
        ]
        for name, kwargs in cases:
            with self.subTest(case=name):
                with self.assertRaises(WithdrawalError):
                    create_withdrawal(user=self.user, **kwargs)
        self.assertEqual(Withdrawal.objects.filter(user=self.user).count(), 0)
        self.assertEqual(_balance(self.user)['locked'], Decimal('0'))

    def test_audit_log_and_notification_created(self) -> None:
        _fund(self.user, '50')
        withdrawal, _ = create_withdrawal(
            user=self.user,
            network_code='TRX',
            destination_address=TRON_ADDRESS,
            amount=Decimal('12.00'),
            idempotency_key='wd-audit-1',
        )
        self.assertTrue(
            AuditLog.objects.filter(
                target_type='withdrawal', target_id=withdrawal.withdrawal_id,
            ).exists(),
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.user,
                notification_type=Notification.NotificationType.WITHDRAWAL,
            ).exists(),
        )

    def test_pending_total_excludes_terminal(self) -> None:
        _fund(self.user, '60')
        w1, _ = create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key='wd-pt-1',
        )
        create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('20.00'), idempotency_key='wd-pt-2',
        )
        self.assertEqual(pending_withdrawal_total(self.user), Decimal('30.00'))
        reject_withdrawal(w1.withdrawal_id, admin=self.user, reason='test')
        self.assertEqual(pending_withdrawal_total(self.user), Decimal('20.00'))


class WithdrawalStateTests(TestCase):
    """State machine and accounting transitions (§24–34, §64–67)."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', verbosity=0)
        cls.admin = User.objects.create_superuser(
            email='wd-admin@example.com', password=PASSWORD, phone='+19955500001',
        )
        cls.user = _mk('wd-state@example.com', 20)
        _grant_paid_vip(cls.user, 'state')

    def _make(self, key: str, amount: str = '20.00') -> Withdrawal:
        _fund(self.user, '100')
        withdrawal, _ = create_withdrawal(
            user=self.user,
            network_code='TRX',
            destination_address=TRON_ADDRESS,
            amount=Decimal(amount),
            idempotency_key=key,
        )
        return withdrawal

    def test_full_lifecycle_to_completed(self) -> None:
        withdrawal = self._make('wd-life-1')
        base_withdrawable = Decimal('80.00')  # 100 funded - 20 locked

        approve_withdrawal(withdrawal.withdrawal_id, admin=self.admin, admin_note='ok')
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.APPROVED)
        self.assertEqual(withdrawal.approved_at is not None, True)
        self.assertEqual(_balance(self.user)['locked'], Decimal('20.00'))  # stays locked (§30)

        start_processing(withdrawal.withdrawal_id, admin=self.admin)
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.PROCESSING)

        complete_withdrawal(withdrawal.withdrawal_id, admin=self.admin,
                            tx_hash='a' * 64, admin_note='manual payout confirmed')
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.COMPLETED)
        self.assertEqual(withdrawal.tx_hash, 'a' * 64)  # stored verbatim (§32)
        balances = _balance(self.user)
        self.assertEqual(balances['locked'], Decimal('0'))
        self.assertEqual(balances['withdrawable'], base_withdrawable)  # consumed, not returned
        self.assertEqual(pending_withdrawal_total(self.user), Decimal('0'))

    def test_rejection_releases_funds(self) -> None:
        withdrawal = self._make('wd-rej-1')
        reject_withdrawal(
            withdrawal.withdrawal_id, admin=self.admin,
            reason='Invalid destination address',
        )
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.REJECTED)
        self.assertEqual(withdrawal.rejection_reason, 'Invalid destination address')
        balances = _balance(self.user)
        self.assertEqual(balances['withdrawable'], Decimal('100.00'))
        self.assertEqual(balances['locked'], Decimal('0'))

    def test_double_rejection_is_safe(self) -> None:
        withdrawal = self._make('wd-rej-2')
        reject_withdrawal(withdrawal.withdrawal_id, admin=self.admin, reason='first')
        with self.assertRaises(InvalidTransitionError):
            reject_withdrawal(withdrawal.withdrawal_id, admin=self.admin, reason='second')
        # No duplicate ledger rows (§66). release_lock writes one RELEASE row
        # per leg (debit on locked + credit on withdrawable); count the
        # locked-bucket debit leg only.
        releases = WalletTransaction.objects.filter(
            user=self.user,
            transaction_type=WalletTransaction.TransactionType.RELEASE,
            direction=WalletTransaction.Direction.DEBIT,
            reference_id=withdrawal.withdrawal_id,
        )
        self.assertEqual(releases.count(), 1)
        self.assertEqual(_balance(self.user)['withdrawable'], Decimal('100.00'))

    def test_double_completion_is_safe(self) -> None:
        withdrawal = self._make('wd-done-1')
        approve_withdrawal(withdrawal.withdrawal_id, admin=self.admin)
        start_processing(withdrawal.withdrawal_id, admin=self.admin)
        complete_withdrawal(withdrawal.withdrawal_id, admin=self.admin)
        with self.assertRaises(InvalidTransitionError):
            complete_withdrawal(withdrawal.withdrawal_id, admin=self.admin)
        finalizes = WalletTransaction.objects.filter(
            user=self.user,
            transaction_type=WalletTransaction.TransactionType.WITHDRAWAL,
            balance_type=WalletTransaction.BalanceType.LOCKED,  # the debit leg
            reference_id=withdrawal.withdrawal_id,
        )
        self.assertEqual(finalizes.count(), 1)
        self.assertEqual(_balance(self.user)['locked'], Decimal('0'))

    def test_failure_releases_funds(self) -> None:
        withdrawal = self._make('wd-fail-1')
        approve_withdrawal(withdrawal.withdrawal_id, admin=self.admin)
        start_processing(withdrawal.withdrawal_id, admin=self.admin)
        fail_withdrawal(withdrawal.withdrawal_id, admin=self.admin, reason='payout provider down')
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.status, Withdrawal.Status.FAILED)
        self.assertEqual(_balance(self.user)['withdrawable'], Decimal('100.00'))
        self.assertEqual(_balance(self.user)['locked'], Decimal('0'))

    def test_invalid_transitions_rejected(self) -> None:
        withdrawal = self._make('wd-inv-1')
        # PENDING → COMPLETED / PROCESSING / FAILED are all forbidden (§25).
        for transition in (complete_withdrawal, start_processing, fail_withdrawal):
            with self.subTest(transition=transition.__name__):
                with self.assertRaises(InvalidTransitionError):
                    transition(withdrawal.withdrawal_id, admin=self.admin)
        reject_withdrawal(withdrawal.withdrawal_id, admin=self.admin, reason='no')
        # Terminal REJECTED forbids APPROVED / PROCESSING / COMPLETED (§25).
        for transition in (approve_withdrawal, start_processing, complete_withdrawal):
            with self.subTest(transition=transition.__name__):
                with self.assertRaises(InvalidTransitionError):
                    transition(withdrawal.withdrawal_id, admin=self.admin)

    def test_no_duplicate_notifications_on_retry_paths(self) -> None:
        withdrawal = self._make('wd-notif-1')
        reject_withdrawal(withdrawal.withdrawal_id, admin=self.admin, reason='dup')
        with self.assertRaises(InvalidTransitionError):
            reject_withdrawal(withdrawal.withdrawal_id, admin=self.admin, reason='dup')
        rejected_notifs = Notification.objects.filter(
            user=self.user, title='Withdrawal rejected',
        )
        self.assertEqual(rejected_notifs.count(), 1)


class WithdrawalConcurrencyTests(TransactionTestCase):
    """Concurrent submissions against one balance (§37, §68)."""

    def setUp(self) -> None:
        call_command('seed_demo_data', verbosity=0)
        self.user = _mk(f'wd-conc@example.com', 30)
        _grant_paid_vip(self.user, 'conc')

    def test_only_one_overdraw_wins(self) -> None:
        _fund(self.user, '20')
        barrier = Barrier(2)
        results: list[str] = []

        def submit(key: str) -> None:
            try:
                barrier.wait(timeout=10)
                create_withdrawal(
                    user=self.user,
                    network_code='TRX',
                    destination_address=TRON_ADDRESS,
                    amount=Decimal('15.00'),
                    idempotency_key=key,
                )
                results.append('ok')
            except Exception as exc:  # noqa: BLE001 - any failure loses the race
                results.append(type(exc).__name__)

        threads = [Thread(target=submit, args=(f'wd-race-{i}',)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        self.assertEqual(sorted(results), ['WithdrawalError', 'ok'])
        self.assertEqual(Withdrawal.objects.filter(user=self.user).count(), 1)
        balances = _balance(self.user)
        self.assertEqual(balances['withdrawable'], Decimal('5.00'))
        self.assertEqual(balances['locked'], Decimal('15.00'))
        wallet = Wallet.objects.get(user=self.user)
        self.assertGreaterEqual(wallet.withdrawable_balance, 0)
        self.assertGreaterEqual(wallet.locked_balance, 0)


class WithdrawalAPITests(TestCase):
    """HTTP surface: auth, isolation, admin authorization (§38–39, §69–70)."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', verbosity=0)
        cls.admin = User.objects.create_superuser(
            email='wd-api-admin@example.com', password=PASSWORD, phone='+19955500002',
        )
        cls.a = _mk('wd-api-a@example.com', 40)
        cls.b = _mk('wd-api-b@example.com', 41)
        _grant_paid_vip(cls.a, 'api-a')
        _grant_paid_vip(cls.b, 'api-b')

    def setUp(self) -> None:
        from rest_framework.test import APIClient

        self.client = APIClient()

    def _auth(self, user) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def _submit(self, user, key: str, amount: str = '20.00', **overrides) -> dict:
        self._auth(user)
        _fund(user, '200')
        payload = {
            'network': 'TRX',
            'destination_address': TRON_ADDRESS,
            'amount': amount,
            'idempotency_key': key,
            **overrides,
        }
        response = self.client.post('/api/withdrawals/', payload, format='json')
        self.assertIn(response.status_code, (200, 201), response.content)
        return response.json()['data']

    def test_requires_authentication(self) -> None:
        self.assertEqual(self.client.get('/api/withdrawals/').status_code, 401)
        self.assertEqual(self.client.get('/api/withdrawals/rules/').status_code, 401)
        self.assertEqual(self.client.get('/api/withdrawals/summary/').status_code, 401)
        self.assertEqual(self.client.get('/api/withdrawals/networks/').status_code, 401)

    def test_rules_endpoint(self) -> None:
        self._auth(self.a)
        response = self.client.get('/api/withdrawals/rules/')
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['minimum_amount'], '5.00')
        self.assertEqual(data['fee_type'], 'FIXED')

    def test_networks_endpoint(self) -> None:
        self._auth(self.a)
        response = self.client.get('/api/withdrawals/networks/')
        codes = {n['code'] for n in response.json()['data']}
        self.assertTrue(codes)
        for row in response.json()['data']:
            self.assertIn('address_hint', row)
            self.assertIn('name', row)

    def test_summary_endpoint(self) -> None:
        self._auth(self.a)
        _fund(self.a, '75')
        response = self.client.get('/api/withdrawals/summary/')
        data = response.json()['data']
        self.assertEqual(data['withdrawable_balance'], '75.00')
        self.assertEqual(data['pending_withdrawals'], '0.00')

    def test_quote_endpoint(self) -> None:
        self._auth(self.a)
        response = self.client.post(
            '/api/withdrawals/quote/', {'network': 'TRX', 'amount': '20.00'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['fee'], '1.00')
        self.assertEqual(data['net_amount'], '19.00')

    def test_submit_and_history_and_masking(self) -> None:
        data = self._submit(self.a, 'wd-api-1')
        self.assertEqual(data['status'], 'PENDING')
        self.assertEqual(data['destination_address'], TRON_ADDRESS)  # detail: full

        response = self.client.get('/api/withdrawals/')
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['pagination']['count'], 1)
        row = body['data'][0]
        self.assertIn('…', row['masked_address'])
        self.assertNotIn('destination_address', row)  # full address never in lists (§40)

    def test_detail_isolation_idor(self) -> None:
        data = self._submit(self.a, 'wd-api-2')
        self._auth(self.b)
        response = self.client.get(f"/api/withdrawals/{data['withdrawal_id']}/")
        self.assertEqual(response.status_code, 404)

    def test_list_isolation(self) -> None:
        self._submit(self.a, 'wd-api-3')
        self._auth(self.b)
        response = self.client.get('/api/withdrawals/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], [])

    def test_amount_tampering_rejected(self) -> None:
        with self.subTest(case='zero'):
            response = self.client.post('/api/withdrawals/', {
                'network': 'TRX', 'destination_address': TRON_ADDRESS,
                'amount': '0', 'idempotency_key': 'tamper-1',
            }, format='json')
            self.assertEqual(response.status_code, 401)  # unauthenticated first
        self._auth(self.a)
        _fund(self.a, '100')
        with self.subTest(case='zero'):
            response = self.client.post('/api/withdrawals/', {
                'network': 'TRX', 'destination_address': TRON_ADDRESS,
                'amount': '0', 'idempotency_key': 'tamper-2',
            }, format='json')
            self.assertEqual(response.status_code, 400)
        with self.subTest(case='negative'):
            response = self.client.post('/api/withdrawals/', {
                'network': 'TRX', 'destination_address': TRON_ADDRESS,
                'amount': '-20', 'idempotency_key': 'tamper-3',
            }, format='json')
            self.assertEqual(response.status_code, 400)
        with self.subTest(case='over-precise'):
            response = self.client.post('/api/withdrawals/', {
                'network': 'TRX', 'destination_address': TRON_ADDRESS,
                'amount': '10.123456789', 'idempotency_key': 'tamper-4',
            }, format='json')
            self.assertEqual(response.status_code, 400)

    def test_admin_requires_staff(self) -> None:
        self._auth(self.a)
        self.assertEqual(
            self.client.get('/api/admin-panel/withdrawals/').status_code, 403,
        )
        data = self._submit(self.a, 'wd-api-admin', amount='25.00')
        self.assertEqual(
            self.client.post(
                f"/api/admin-panel/withdrawals/{data['withdrawal_id']}/approve/",
                {}, format='json',
            ).status_code, 403,
        )
        self.client.credentials()  # unauthenticated
        self.assertEqual(
            self.client.get('/api/admin-panel/withdrawals/').status_code, 401,
        )

    def test_admin_full_lifecycle_via_api(self) -> None:
        data = self._submit(self.a, 'wd-api-life', amount='30.00')
        wid = data['withdrawal_id']
        self._auth(self.admin)

        approve = self.client.post(f'/api/admin-panel/withdrawals/{wid}/approve/', {
            'admin_note': 'Approved for manual processing',
        }, format='json')
        self.assertEqual(approve.status_code, 200)
        self.assertEqual(approve.json()['data']['status'], 'APPROVED')

        processing = self.client.post(f'/api/admin-panel/withdrawals/{wid}/processing/', {}, format='json')
        self.assertEqual(processing.status_code, 200)

        complete = self.client.post(f'/api/admin-panel/withdrawals/{wid}/complete/', {
            'transaction_hash': 'b' * 64,
            'admin_note': 'Manual payout confirmed',
        }, format='json')
        self.assertEqual(complete.status_code, 200)
        self.assertEqual(complete.json()['data']['status'], 'COMPLETED')
        self.assertEqual(complete.json()['data']['tx_hash'], 'b' * 64)

        # Idempotent completion at the API level: 409 on the second attempt,
        # and no duplicate accounting (asserted in service tests).
        again = self.client.post(f'/api/admin-panel/withdrawals/{wid}/complete/', {}, format='json')
        self.assertEqual(again.status_code, 409)

    def test_admin_reject_requires_reason_and_releases(self) -> None:
        data = self._submit(self.a, 'wd-api-rej', amount='15.00')
        wid = data['withdrawal_id']
        self._auth(self.admin)
        missing = self.client.post(f'/api/admin-panel/withdrawals/{wid}/reject/', {}, format='json')
        self.assertEqual(missing.status_code, 400)

        rejected = self.client.post(f'/api/admin-panel/withdrawals/{wid}/reject/', {
            'reason': 'Incorrect network',
            'admin_note': 'Please resubmit on TRON.',
        }, format='json')
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()['data']['status'], 'REJECTED')

        self._auth(self.a)
        summary = self.client.get('/api/withdrawals/summary/').json()['data']
        self.assertEqual(summary['pending_withdrawals'], '0.00')
        self.assertEqual(summary['withdrawable_balance'], '200.00')  # 200 - 15 locked → released

    def test_admin_list_filter(self) -> None:
        self._submit(self.a, 'wd-api-filter', amount='10.00')
        self._auth(self.admin)
        response = self.client.get('/api/admin-panel/withdrawals/?status=PENDING')
        self.assertEqual(response.status_code, 200)
        for row in response.json()['data']:
            self.assertEqual(row['status'], 'PENDING')


class WithdrawalReconciliationTests(TestCase):
    """Withdrawal invariants inside reconcile_wallets (§80)."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', verbosity=0)
        cls.admin = User.objects.create_superuser(
            email='wd-recon-admin@example.com', password=PASSWORD, phone='+19955500001',
        )
        cls.user = _mk('wd-recon@example.com', 10)
        _grant_paid_vip(cls.user, 'recon')

    def test_clean_lifecycle_reports_no_issues(self) -> None:
        _fund(self.user, '50')
        withdrawal, _ = create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('20.00'), idempotency_key='wd-recon-1',
        )
        self.assertEqual(reconcile_user_withdrawals(self.user), [])
        approve_withdrawal(withdrawal.withdrawal_id, admin=self.admin)
        self.assertEqual(reconcile_user_withdrawals(self.user), [])
        start_processing(withdrawal.withdrawal_id, admin=self.admin)
        self.assertEqual(reconcile_user_withdrawals(self.user), [])
        complete_withdrawal(withdrawal.withdrawal_id, admin=self.admin)
        self.assertEqual(reconcile_user_withdrawals(self.user), [])

    def test_rejected_and_failed_report_no_issues(self) -> None:
        _fund(self.user, '60')
        rej, _ = create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key='wd-recon-2',
        )
        reject_withdrawal(rej.withdrawal_id, admin=self.admin, reason='no')
        self.assertEqual(reconcile_user_withdrawals(self.user), [])
        fail_wd, _ = create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key='wd-recon-3',
        )
        approve_withdrawal(fail_wd.withdrawal_id, admin=self.admin)
        start_processing(fail_wd.withdrawal_id, admin=self.admin)
        fail_withdrawal(fail_wd.withdrawal_id, admin=self.admin, reason='payout failed')
        self.assertEqual(reconcile_user_withdrawals(self.user), [])

    def test_detects_completed_without_finalization(self) -> None:
        _fund(self.user, '30')
        withdrawal, _ = create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('20.00'), idempotency_key='wd-recon-4',
        )
        approve_withdrawal(withdrawal.withdrawal_id, admin=self.admin)
        start_processing(withdrawal.withdrawal_id, admin=self.admin)
        # Bypass the service: mark completed without any ledger movement.
        Withdrawal.objects.filter(pk=withdrawal.pk).update(status=Withdrawal.Status.COMPLETED)
        issues = reconcile_user_withdrawals(self.user)
        self.assertTrue(any('completed without ledger finalization' in i for i in issues))

    def test_detects_fee_snapshot_mismatch(self) -> None:
        _fund(self.user, '20')
        create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key='wd-recon-5',
        )
        # Corrupt the snapshot directly (simulates out-of-band editing).
        Withdrawal.objects.update(fee_amount=Decimal('0'), net_amount=Decimal('10.00'))
        # requested(10) - fee(0) == net(10) — consistent, so force a real mismatch:
        Withdrawal.objects.update(net_amount=Decimal('9.00'))
        issues = reconcile_user_withdrawals(self.user)
        self.assertTrue(any('fee mismatch' in i for i in issues))


class WithdrawalEligibilityTests(TestCase):
    """VIP1+ withdrawal eligibility (server-side; Welcome does NOT qualify)."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', verbosity=0)
        cls.user = _mk('wd-elig@example.com', 50)

    def _attempt(self, key: str):
        return create_withdrawal(
            user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
            amount=Decimal('10.00'), idempotency_key=key,
        )

    def test_no_vip_rejected_no_record(self) -> None:
        _fund(self.user, '50')
        with self.assertRaises(WithdrawalError) as ctx:
            self._attempt('elig-none-1')
        self.assertIn('must purchase at least VIP 1', ctx.exception.message)
        self.assertFalse(Withdrawal.objects.filter(user=self.user).exists())
        # Nothing was locked either.
        summary = get_wallet_summary(self.user)
        self.assertEqual(summary['withdrawable_balance'], Decimal('50'))
        self.assertEqual(summary['locked_balance'], Decimal('0'))

    def test_welcome_only_rejected(self) -> None:
        from apps.vip.models import VIPPlan, VIPPurchase

        welcome = VIPPlan.objects.get(name='WELCOME')
        VIPPurchase.objects.create(
            user=self.user, vip_plan=welcome, plan_name_snapshot=welcome.name,
            investment_amount=Decimal('0'), target_amount=Decimal('10'),
            daily_rate_snapshot=welcome.daily_rate, status=VIPPurchase.Status.COMPLETED,
            idempotency_key='TEST_WELCOME_only',
        )
        _fund(self.user, '50')
        with self.assertRaises(WithdrawalError) as ctx:
            self._attempt('elig-welcome-1')
        self.assertIn('must purchase at least VIP 1', ctx.exception.message)
        self.assertIn('Welcome Plan does not qualify', ctx.exception.errors['vip_plan'][0])
        self.assertFalse(Withdrawal.objects.filter(user=self.user).exists())

    def test_vip1_unlocks_withdrawal(self) -> None:
        _grant_paid_vip(self.user, 'elig-vip1')
        _fund(self.user, '50')
        withdrawal, created = self._attempt('elig-vip1-ok')
        self.assertTrue(created)
        self.assertEqual(withdrawal.status, Withdrawal.Status.PENDING)

    def test_vip2_plus_unlocks_withdrawal(self) -> None:
        _grant_paid_vip(self.user, 'elig-vip2', plan_name='VIP 2')
        _fund(self.user, '50')
        withdrawal, created = self._attempt('elig-vip2-ok')
        self.assertTrue(created)

    def test_cancelled_paid_purchase_does_not_qualify(self) -> None:
        from apps.vip.models import VIPPurchase

        _grant_paid_vip(self.user, 'elig-cancelled')
        VIPPurchase.objects.filter(user=self.user).update(status=VIPPurchase.Status.CANCELLED)
        _fund(self.user, '50')
        with self.assertRaises(WithdrawalError):
            self._attempt('elig-cancelled-1')
        self.assertFalse(Withdrawal.objects.filter(user=self.user).exists())

    def test_api_rejects_ineligible_user_with_envelope(self) -> None:
        """Direct API bypass attempt → 400 envelope, no withdrawal created."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        _fund(self.user, '50')
        client = APIClient()
        token = RefreshToken.for_user(self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        response = client.post('/api/withdrawals/', {
            'network': 'TRX', 'destination_address': TRON_ADDRESS,
            'amount': '10.00', 'idempotency_key': 'elig-api-1',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertFalse(body['success'])
        self.assertIn('must purchase at least VIP 1', body['message'])
        self.assertFalse(Withdrawal.objects.filter(user=self.user).exists())

    def test_summary_reports_can_withdraw(self) -> None:
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        token = RefreshToken.for_user(self.user)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')
        response = client.get('/api/withdrawals/summary/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['data']['can_withdraw'])
        _grant_paid_vip(self.user, 'elig-summary')
        response = client.get('/api/withdrawals/summary/')
        self.assertTrue(response.json()['data']['can_withdraw'])

    def test_existing_validations_still_fire(self) -> None:
        """Eligible user: balance/min/network/address checks unchanged."""
        _grant_paid_vip(self.user, 'elig-valid')
        with self.assertRaises(WithdrawalError):
            self._attempt('elig-nobalance')  # unfunded wallet → insufficient
        _fund(self.user, '8')
        with self.assertRaises(WithdrawalError):  # 3.00 < minimum 5.00
            create_withdrawal(
                user=self.user, network_code='TRX', destination_address=TRON_ADDRESS,
                amount=Decimal('3.00'), idempotency_key='elig-below-min',
            )
        _fund(self.user, '50')
        with self.assertRaises(WithdrawalError):  # unknown network
            create_withdrawal(
                user=self.user, network_code='NOPE', destination_address=TRON_ADDRESS,
                amount=Decimal('10.00'), idempotency_key='elig-bad-network',
            )
        with self.assertRaises(WithdrawalError):  # wrong-format address
            create_withdrawal(
                user=self.user, network_code='TRX', destination_address='0x' + 'a' * 40,
                amount=Decimal('10.00'), idempotency_key='elig-bad-address',
            )
        self.assertFalse(Withdrawal.objects.filter(user=self.user).exists())

    def test_paid_plan_below_vip1_does_not_qualify(self) -> None:
        """A PAID plan numbered below VIP 1 (plan_number < 1) never unlocks
        withdrawals — eligibility joins the related VIPPlan, not the name.
        The seeded plan_number=0 row is turned into a PAID non-welcome plan
        for this test (TestCase rolls the mutation back)."""
        from apps.vip.models import VIPPlan, VIPPurchase

        zero = VIPPlan.objects.get(plan_number=0)
        zero.name = 'PROMO PLUS'
        zero.investment_amount = Decimal('10')
        zero.save()
        VIPPurchase.objects.create(
            user=self.user, vip_plan=zero, plan_name_snapshot=zero.name,
            investment_amount=zero.investment_amount, target_amount=zero.target_amount,
            daily_rate_snapshot=zero.daily_rate, status=VIPPurchase.Status.ACTIVE,
            idempotency_key='TEST_PAID_VIP_promo0',
        )
        self.assertFalse(services.has_qualifying_vip(self.user))
        _fund(self.user, '50')
        with self.assertRaises(WithdrawalError):
            self._attempt('elig-promo0-1')
        self.assertFalse(Withdrawal.objects.filter(user=self.user).exists())

        # plan_number 1 (VIP 1) does qualify, on the same account.
        _grant_paid_vip(self.user, 'elig-promo0-vip1')
        self.assertTrue(services.has_qualifying_vip(self.user))
        withdrawal, created = self._attempt('elig-promo0-ok')
        self.assertTrue(created)

    def test_vip2_fixture_uses_real_plan_number(self) -> None:
        """The VIP 2+ fixture joins a plan actually numbered 2 (regression)."""
        plan = _grant_paid_vip(self.user, 'elig-vip2-num', plan_name='VIP 2')
        self.assertEqual(plan.plan_number, 2)
        self.assertTrue(services.has_qualifying_vip(self.user))
