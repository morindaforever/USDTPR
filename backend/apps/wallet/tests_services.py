"""Service-layer tests for the wallet ledger system (Section 5)."""

from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError
from django.test import TestCase

from apps.accounts.models import User
from apps.core.models import AuditLog
from apps.wallet.models import Wallet, WalletTransaction
from apps.wallet.services import (
    DuplicateTransactionError,
    InsufficientBalanceError,
    InvalidAmountError,
    InvalidBalanceTypeError,
    InvalidTransactionError,
    admin_adjust,
    credit,
    debit,
    ensure_wallet,
    finalize_locked,
    get_wallet_summary,
    lock,
    reconcile_wallet,
    release_lock,
    reverse_transaction,
    transfer_between_balances,
)

BT = WalletTransaction.BalanceType
TT = WalletTransaction.TransactionType
D = WalletTransaction.Direction


class WalletServiceTestBase(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='wallet@example.com', password='S3curePass!', phone='+15550200001', full_name='Wallet User'
        )
        # Registration creates wallets in production; tests do it explicitly.
        self.wallet = Wallet.objects.create(user=self.user)

    def balance(self, field: str) -> Decimal:
        self.wallet.refresh_from_db()
        return getattr(self.wallet, field)


class WalletCreationTests(WalletServiceTestBase):
    def test_ensure_wallet_creates_once(self) -> None:
        first = ensure_wallet(self.user)
        second = ensure_wallet(self.user)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Wallet.objects.filter(user=self.user).count(), 1)

    def test_duplicate_wallet_rejected_by_db(self) -> None:
        with self.assertRaises(IntegrityError):
            Wallet.objects.create(user=self.user)

    def test_summary_defaults_to_zero(self) -> None:
        summary = get_wallet_summary(self.user)
        for value in summary.values():
            self.assertEqual(value, Decimal('0'))


class CreditTests(WalletServiceTestBase):
    def test_credit_updates_wallet_and_ledger(self) -> None:
        ledger = credit(
            user=self.user, amount='50.00', balance_type=BT.DEPOSIT,
            transaction_type=TT.DEPOSIT, reference_type='deposit', reference_id='DEP000123',
            description='USDT deposit', idempotency_key='test-credit-1',
        )
        self.assertEqual(self.balance('deposit_balance'), Decimal('50.00000000'))
        self.assertEqual(self.balance('total_balance'), Decimal('50.00000000'))
        self.assertEqual(ledger.status, WalletTransaction.Status.COMPLETED)
        self.assertEqual(ledger.direction, D.CREDIT)
        self.assertEqual(ledger.reference_id, 'DEP000123')

    def test_credit_rejects_float(self) -> None:
        with self.assertRaises(InvalidAmountError):
            credit(user=self.user, amount=0.1, balance_type=BT.DEPOSIT, transaction_type=TT.DEPOSIT)

    def test_credit_rejects_zero_and_negative(self) -> None:
        for bad in ('0', '-5'):
            with self.assertRaises(InvalidAmountError):
                credit(user=self.user, amount=bad, balance_type=BT.DEPOSIT, transaction_type=TT.DEPOSIT)

    def test_credit_rejects_total_bucket(self) -> None:
        with self.assertRaises(InvalidBalanceTypeError):
            credit(user=self.user, amount='5', balance_type=BT.TOTAL, transaction_type=TT.ADJUSTMENT)

    def test_credit_idempotency_returns_same_row(self) -> None:
        first = credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
                       transaction_type=TT.DEPOSIT, idempotency_key='TEST123')
        second = credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
                        transaction_type=TT.DEPOSIT, idempotency_key='TEST123')
        self.assertEqual(first.transaction_id, second.transaction_id)
        self.assertEqual(self.balance('deposit_balance'), Decimal('50.00000000'))
        self.assertEqual(WalletTransaction.objects.filter(user=self.user).count(), 1)

    def test_credit_pending_key_conflicts(self) -> None:
        """A non-COMPLETED row holding the key blocks re-use (unique constraint)."""
        WalletTransaction.objects.create(
            user=self.user, transaction_type=TT.DEPOSIT, direction=D.CREDIT,
            balance_type=BT.DEPOSIT, amount=Decimal('10'), status=WalletTransaction.Status.PENDING,
            idempotency_key='taken-key',
        )
        with self.assertRaises(DuplicateTransactionError):
            credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
                   transaction_type=TT.DEPOSIT, idempotency_key='taken-key')


class DebitTests(WalletServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        credit(user=self.user, amount='100', balance_type=BT.WITHDRAWABLE,
               transaction_type=TT.ADJUSTMENT, idempotency_key='seed-100')

    def test_debit_updates_wallet_and_ledger(self) -> None:
        ledger = debit(user=self.user, amount='30', balance_type=BT.WITHDRAWABLE,
                       transaction_type=TT.WITHDRAWAL, idempotency_key='debit-1')
        self.assertEqual(self.balance('withdrawable_balance'), Decimal('70.00000000'))
        self.assertEqual(self.balance('total_balance'), Decimal('70.00000000'))
        self.assertEqual(ledger.direction, D.DEBIT)

    def test_insufficient_balance_rejected(self) -> None:
        with self.assertRaises(InsufficientBalanceError):
            debit(user=self.user, amount='150', balance_type=BT.WITHDRAWABLE,
                  transaction_type=TT.WITHDRAWAL, idempotency_key='too-much')
        self.assertEqual(self.balance('withdrawable_balance'), Decimal('100.00000000'))
        rejected = WalletTransaction.objects.filter(
            user=self.user, idempotency_key='too-much', status=WalletTransaction.Status.COMPLETED,
        ).exists()
        self.assertFalse(rejected)


class AtomicityTests(WalletServiceTestBase):
    """A failure anywhere rolls back BOTH ledger and wallet."""

    def test_error_after_ledger_rolls_back_everything(self) -> None:
        with patch.object(Wallet, 'save', side_effect=RuntimeError('boom after ledger')):
            with self.assertRaises(RuntimeError):
                credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
                       transaction_type=TT.DEPOSIT, idempotency_key='atomic-1')
        self.assertEqual(self.balance('deposit_balance'), Decimal('0'))
        self.assertFalse(WalletTransaction.objects.filter(user=self.user).exists())

    def test_error_before_wallet_update_rolls_back_everything(self) -> None:
        credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, idempotency_key='atomic-seed')
        with patch.object(WalletTransaction.objects, 'create', side_effect=RuntimeError('boom before wallet')):
            with self.assertRaises(RuntimeError):
                debit(user=self.user, amount='10', balance_type=BT.DEPOSIT,
                      transaction_type=TT.WITHDRAWAL, idempotency_key='atomic-2')
        self.assertEqual(self.balance('deposit_balance'), Decimal('50.00000000'))
        self.assertEqual(WalletTransaction.objects.filter(user=self.user).count(), 1)


class LockReleaseTests(WalletServiceTestBase):
    def setUp(self) -> None:
        super().setUp()
        credit(user=self.user, amount='100', balance_type=BT.WITHDRAWABLE,
               transaction_type=TT.ADJUSTMENT, idempotency_key='seed-lock')

    def test_lock_moves_withdrawable_to_locked(self) -> None:
        lock(user=self.user, amount='40', reference_type='withdrawal',
             reference_id='WDR000001', idempotency_key='lock-1')
        self.assertEqual(self.balance('withdrawable_balance'), Decimal('60.00000000'))
        self.assertEqual(self.balance('locked_balance'), Decimal('40.00000000'))
        self.assertEqual(self.balance('total_balance'), Decimal('100.00000000'))
        # Both legs are in the ledger.
        legs = WalletTransaction.objects.filter(
            user=self.user, transaction_type=TT.LOCK, reference_id='WDR000001',
        )
        self.assertEqual(legs.count(), 2)
        self.assertCountEqual(legs.values_list('direction', flat=True), [D.DEBIT, D.CREDIT])

    def test_release_returns_locked_funds(self) -> None:
        lock(user=self.user, amount='40', idempotency_key='lock-2')
        release_lock(user=self.user, amount='40', idempotency_key='release-1')
        self.assertEqual(self.balance('withdrawable_balance'), Decimal('100.00000000'))
        self.assertEqual(self.balance('locked_balance'), Decimal('0.00000000'))

    def test_lock_insufficient(self) -> None:
        with self.assertRaises(InsufficientBalanceError):
            lock(user=self.user, amount='200', idempotency_key='lock-3')
        self.assertEqual(self.balance('withdrawable_balance'), Decimal('100.00000000'))
        self.assertEqual(self.balance('locked_balance'), Decimal('0.00000000'))

    def test_release_insufficient_locked(self) -> None:
        with self.assertRaises(InsufficientBalanceError):
            release_lock(user=self.user, amount='25', idempotency_key='release-2')

    def test_finalize_locked_reduces_holdings(self) -> None:
        lock(user=self.user, amount='40', reference_type='withdrawal',
             reference_id='WDR000002', idempotency_key='lock-4')
        finalize_locked(user=self.user, amount='40', reference_type='withdrawal',
                        reference_id='WDR000002', idempotency_key='final-1')
        self.assertEqual(self.balance('locked_balance'), Decimal('0.00000000'))
        self.assertEqual(self.balance('withdrawable_balance'), Decimal('60.00000000'))
        self.assertEqual(self.balance('total_balance'), Decimal('60.00000000'))


class TransferTests(WalletServiceTestBase):
    def test_transfer_between_buckets(self) -> None:
        credit(user=self.user, amount='50', balance_type=BT.BONUS,
               transaction_type=TT.WELCOME_BONUS, idempotency_key='seed-bonus')
        transfer_between_balances(
            user=self.user, amount='10', from_balance_type=BT.BONUS,
            to_balance_type=BT.WITHDRAWABLE, idempotency_key='xfer-1',
        )
        self.assertEqual(self.balance('bonus_balance'), Decimal('40.00000000'))
        self.assertEqual(self.balance('withdrawable_balance'), Decimal('10.00000000'))
        self.assertEqual(self.balance('total_balance'), Decimal('50.00000000'))

    def test_transfer_rejects_total_and_same_bucket(self) -> None:
        with self.assertRaises(InvalidBalanceTypeError):
            transfer_between_balances(user=self.user, amount='5',
                                      from_balance_type=BT.BONUS, to_balance_type=BT.BONUS)
        with self.assertRaises(InvalidBalanceTypeError):
            transfer_between_balances(user=self.user, amount='5',
                                      from_balance_type=BT.BONUS, to_balance_type=BT.TOTAL)


class DecimalPrecisionTests(WalletServiceTestBase):
    def test_precision_preserved(self) -> None:
        amounts = ['0.00000001', '1.12345678', '50.50000000', '999999.99999999']
        for i, amount in enumerate(amounts):
            credit(user=self.user, amount=amount, balance_type=BT.DEPOSIT,
                   transaction_type=TT.DEPOSIT, idempotency_key=f'prec-{i}')
        expected = sum(Decimal(a) for a in amounts)
        self.assertEqual(self.balance('deposit_balance'), expected.quantize(Decimal('0.00000001')))
        self.assertNotIsInstance(self.balance('deposit_balance'), float)


class AdjustAndReverseTests(WalletServiceTestBase):
    def test_admin_adjust_writes_ledger_and_audit(self) -> None:
        admin_adjust(
            user=self.user, amount='25', balance_type=BT.BONUS,
            direction=D.CREDIT, reason='promo compensation', idempotency_key='adj-1',
        )
        self.assertEqual(self.balance('bonus_balance'), Decimal('25.00000000'))
        self.assertTrue(AuditLog.objects.filter(action=AuditLog.Action.ADJUST, actor_user=None).exists())

    def test_admin_adjust_requires_reason(self) -> None:
        with self.assertRaises(InvalidTransactionError):
            admin_adjust(user=self.user, amount='25', balance_type=BT.BONUS, direction=D.CREDIT, reason='  ')

    def test_reverse_transaction_restores_balance(self) -> None:
        ledger = credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
                        transaction_type=TT.DEPOSIT, idempotency_key='rev-seed')
        reversal = reverse_transaction(ledger=ledger, reason='duplicate deposit', idempotency_key='rev-1')
        self.assertEqual(self.balance('deposit_balance'), Decimal('0.00000000'))
        self.assertEqual(self.balance('total_balance'), Decimal('0.00000000'))
        ledger.refresh_from_db()
        self.assertEqual(ledger.status, WalletTransaction.Status.REVERSED)
        self.assertEqual(reversal.direction, D.DEBIT)
        self.assertEqual(reversal.reference_id, ledger.transaction_id)

    def test_reverse_rejected_for_non_completed(self) -> None:
        pending = WalletTransaction.objects.create(
            user=self.user, transaction_type=TT.DEPOSIT, direction=D.CREDIT,
            balance_type=BT.DEPOSIT, amount=Decimal('10'), status=WalletTransaction.Status.PENDING,
        )
        with self.assertRaises(InvalidTransactionError):
            reverse_transaction(ledger=pending, reason='nope')


class ReconcileTests(WalletServiceTestBase):
    def test_clean_wallet_reconciles(self) -> None:
        credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, idempotency_key='rec-1')
        credit(user=self.user, amount='40', balance_type=BT.WITHDRAWABLE,
               transaction_type=TT.ADJUSTMENT, idempotency_key='rec-1w')
        lock(user=self.user, amount='20', idempotency_key='rec-2')
        report = reconcile_wallet(self.user)
        self.assertTrue(report['ok'], report['issues'])

    def test_detects_ledger_drift(self) -> None:
        credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, idempotency_key='rec-3')
        # Simulate a rogue write that bypassed the service.
        Wallet.objects.filter(user=self.user).update(deposit_balance=Decimal('90'))
        report = reconcile_wallet(self.user)
        self.assertFalse(report['ok'])
        self.assertTrue(any('DEPOSIT' in issue for issue in report['issues']))

    def test_detects_total_invariant_break(self) -> None:
        credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, idempotency_key='rec-4')
        Wallet.objects.filter(user=self.user).update(total_balance=Decimal('999'))
        report = reconcile_wallet(self.user)
        self.assertFalse(report['ok'])
        self.assertTrue(any('TOTAL' in issue for issue in report['issues']))
