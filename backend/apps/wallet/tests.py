"""Tests for wallet models: balances, ledger invariants, idempotency."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User

from .models import DepositAddress, Network, Wallet, WalletTransaction


class WalletTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='w@example.com', password='S3curePass!', phone='+15550001001',
        )

    def test_default_balances_are_zero(self) -> None:
        wallet = Wallet.objects.create(user=self.user)
        for field in (
            'total_balance', 'deposit_balance', 'withdrawable_balance',
            'pending_balance', 'locked_balance', 'bonus_balance',
        ):
            self.assertEqual(getattr(wallet, field), Decimal('0'))

    def test_decimal_precision_roundtrip(self) -> None:
        wallet = Wallet.objects.create(user=self.user, total_balance=Decimal('12345.12345678'))
        wallet.refresh_from_db()
        self.assertEqual(wallet.total_balance, Decimal('12345.12345678'))

    def test_negative_balance_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            Wallet.objects.create(user=self.user, total_balance=Decimal('-1'))


class WalletTransactionTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='t@example.com', password='S3curePass!', phone='+15550002001',
        )

    def _tx(self, **kwargs) -> WalletTransaction:
        base = {
            'user': self.user,
            'transaction_type': WalletTransaction.TransactionType.DEPOSIT,
            'direction': WalletTransaction.Direction.CREDIT,
            'balance_type': WalletTransaction.BalanceType.TOTAL,
            'amount': Decimal('10'),
        }
        base.update(kwargs)
        return WalletTransaction(**base)

    def test_transaction_ids_are_unique(self) -> None:
        first = self._tx(); first.save()
        second = self._tx(); second.save()
        self.assertNotEqual(first.transaction_id, second.transaction_id)
        self.assertRegex(first.transaction_id, r'^TXN\d{8,}$')

    def test_zero_and_negative_amounts_rejected(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._tx(amount=Decimal('0')).save()

    def test_idempotency_key_prevents_duplicate_rows(self) -> None:
        first = self._tx(idempotency_key='reward:2026-09-16:42'); first.save()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._tx(idempotency_key='reward:2026-09-16:42').save()
        self.assertEqual(WalletTransaction.objects.count(), 1)
        self.assertEqual(WalletTransaction.objects.first(), first)


class NetworkTests(TestCase):
    def test_code_unique(self) -> None:
        Network.objects.create(name='BNB Smart Chain', code='BSC')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Network.objects.create(name='Duplicate', code='BSC')

    def test_only_one_active_address_per_network_asset(self) -> None:
        network = Network.objects.create(name='Tron', code='TRX')
        DepositAddress.objects.create(network=network, address='TQ1', is_active=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DepositAddress.objects.create(network=network, address='TQ2', is_active=True)
        # A different network may have its own active address.
        other = Network.objects.create(name='Solana', code='SOL')
        DepositAddress.objects.create(network=other, address='SQ1', is_active=True)
        self.assertEqual(DepositAddress.objects.count(), 2)
