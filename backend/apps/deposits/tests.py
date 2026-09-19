"""Tests for the Deposit model."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.wallet.models import Network

from .models import Deposit


class DepositTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='d@example.com', password='S3curePass!', phone='+15550005001',
        )
        self.network = Network.objects.create(name='BNB Smart Chain', code='BSC')

    def _deposit(self, **kwargs) -> Deposit:
        base = {
            'user': self.user,
            'network': self.network,
            'amount': Decimal('100'),
            'deposit_address': '0xDESTINATION',
        }
        base.update(kwargs)
        return Deposit(**base)

    def test_deposit_ids_unique(self) -> None:
        first = self._deposit(); first.save()
        second = self._deposit(); second.save()
        self.assertNotEqual(first.deposit_id, second.deposit_id)
        self.assertRegex(first.deposit_id, r'^DEP\d{8,}$')

    def test_network_relationship(self) -> None:
        deposit = self._deposit(); deposit.save()
        self.assertEqual(deposit.network.code, 'BSC')
        self.assertIn(deposit, self.network.deposits.all())

    def test_address_preserved_even_if_current_address_changes(self) -> None:
        deposit = self._deposit(); deposit.save()
        # Admin later rotates the active address for the network.
        self.deposit_address_rotated = '0xNEWADDRESS'
        deposit.refresh_from_db()
        self.assertEqual(deposit.deposit_address, '0xDESTINATION')

    def test_order_id_searchable(self) -> None:
        deposit = self._deposit(order_id='ORDER-123'); deposit.save()
        found = Deposit.objects.filter(order_id='ORDER-123')
        self.assertIn(deposit, found)

    def test_positive_amount_required(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._deposit(amount=Decimal('-5')).save()
