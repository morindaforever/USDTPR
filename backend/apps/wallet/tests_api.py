"""API tests for the wallet endpoints (Section 5)."""

from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.wallet.models import Wallet, WalletTransaction
from apps.wallet.services import credit, lock

BT = WalletTransaction.BalanceType
TT = WalletTransaction.TransactionType
D = WalletTransaction.Direction


class WalletApiTestBase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='api@example.com', password='S3curePass!', phone='+15550400001', full_name='API User'
        )
        self.other = User.objects.create_user(
            email='other-api@example.com', password='S3curePass!', phone='+15550400002', full_name='Other User'
        )
        Wallet.objects.create(user=self.user)
        Wallet.objects.create(user=self.other)
        self.client.force_authenticate(user=self.user)


class SummaryApiTests(WalletApiTestBase):
    def test_requires_auth(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/wallet/summary/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_own_balances_only(self) -> None:
        credit(user=self.other, amount='999', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, idempotency_key='iso-1')
        data = self.client.get('/api/wallet/summary/').data['data']
        self.assertEqual(Decimal(data['deposit_balance']), Decimal('0'))
        self.assertEqual(Decimal(data['total_balance']), Decimal('0'))

    def test_summary_reflects_service_credit(self) -> None:
        credit(user=self.user, amount='125.50', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, idempotency_key='sum-1')
        data = self.client.get('/api/wallet/summary/').data['data']
        self.assertEqual(Decimal(data['deposit_balance']), Decimal('125.50000000'))
        self.assertEqual(Decimal(data['total_balance']), Decimal('125.50000000'))

    def test_no_user_id_parameter_hijack(self) -> None:
        credit(user=self.other, amount='777', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, idempotency_key='hijack-1')
        data = self.client.get('/api/wallet/summary/?user_id=anything').data['data']
        self.assertEqual(Decimal(data['total_balance']), Decimal('0'))


class TransactionListApiTests(WalletApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, description='USDT deposit', idempotency_key='t-1')
        credit(user=self.user, amount='18.75', balance_type=BT.BONUS,
               transaction_type=TT.VIP_REWARD, description='Daily reward', idempotency_key='t-2')
        credit(user=self.user, amount='100', balance_type=BT.WITHDRAWABLE,
               transaction_type=TT.ADJUSTMENT, idempotency_key='t-3')
        lock(user=self.user, amount='40', reference_type='withdrawal',
             reference_id='WDR000009', idempotency_key='t-4')
        credit(user=self.other, amount='500', balance_type=BT.DEPOSIT,
               transaction_type=TT.DEPOSIT, idempotency_key='t-other')

    def test_requires_auth(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/wallet/transactions/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_lists_own_rows_with_envelope_and_pagination(self) -> None:
        payload = self.client.get('/api/wallet/transactions/').data
        self.assertTrue(payload['success'])
        self.assertIn('pagination', payload)
        self.assertGreater(payload['pagination']['count'], 0)
        ids = {row['transaction_id'] for row in payload['data']}
        self.assertTrue(all(txn.startswith('TXN') for txn in ids))

    def test_excludes_other_users_rows(self) -> None:
        payload = self.client.get('/api/wallet/transactions/?page_size=100').data
        for row in payload['data']:
            self.assertNotEqual(Decimal(row['amount']), Decimal('500.00000000'))

    def test_amounts_are_strings_not_floats(self) -> None:
        payload = self.client.get('/api/wallet/transactions/').data
        row = payload['data'][0]
        self.assertIsInstance(row['amount'], str)
        self.assertIn('.', row['amount'])

    def test_filter_by_type(self) -> None:
        payload = self.client.get('/api/wallet/transactions/?type=LOCK').data
        self.assertGreaterEqual(len(payload['data']), 2)  # lock produces two legs
        for row in payload['data']:
            self.assertEqual(row['type'], 'LOCK')

    def test_filter_by_type_and_status(self) -> None:
        payload = self.client.get('/api/wallet/transactions/?type=DEPOSIT&status=COMPLETED').data
        self.assertGreaterEqual(len(payload['data']), 1)
        for row in payload['data']:
            self.assertEqual(row['type'], 'DEPOSIT')
            self.assertEqual(row['status'], 'COMPLETED')

    def test_filter_by_direction(self) -> None:
        payload = self.client.get('/api/wallet/transactions/?direction=DEBIT').data
        self.assertGreaterEqual(len(payload['data']), 1)
        for row in payload['data']:
            self.assertEqual(row['direction'], 'DEBIT')

    def test_filter_by_date_range(self) -> None:
        from django.utils import timezone

        today = timezone.localdate().isoformat()
        payload = self.client.get(f'/api/wallet/transactions/?date_from={today}&date_to={today}').data
        self.assertGreaterEqual(payload['pagination']['count'], 5)
        empty = self.client.get('/api/wallet/transactions/?date_from=2020-01-01&date_to=2020-01-02').data
        self.assertEqual(empty['pagination']['count'], 0)

    def test_invalid_date_returns_400(self) -> None:
        response = self.client.get('/api/wallet/transactions/?date_from=not-a-date')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pagination_page_size(self) -> None:
        payload = self.client.get('/api/wallet/transactions/?page_size=2&page=1').data
        self.assertEqual(len(payload['data']), 2)
        self.assertEqual(payload['pagination']['page_size'], 2)
        payload2 = self.client.get('/api/wallet/transactions/?page_size=2&page=2').data
        self.assertEqual(payload2['pagination']['page'], 2)
        self.assertNotEqual(payload['data'][0]['transaction_id'], payload2['data'][0]['transaction_id'])


class TransactionDetailApiTests(WalletApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.txn = credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
                          transaction_type=TT.DEPOSIT, reference_type='deposit',
                          reference_id='DEP000123', description='USDT deposit', idempotency_key='d-1')
        self.other_txn = credit(user=self.other, amount='80', balance_type=BT.DEPOSIT,
                                transaction_type=TT.DEPOSIT, idempotency_key='d-other')

    def test_detail_by_transaction_id(self) -> None:
        response = self.client.get(f'/api/wallet/transactions/{self.txn.transaction_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data['data']
        self.assertEqual(data['transaction_id'], self.txn.transaction_id)
        self.assertEqual(data['reference_id'], 'DEP000123')
        for field in ('type', 'direction', 'amount', 'balance_type', 'status', 'description', 'created_at'):
            self.assertIn(field, data)

    def test_other_users_transaction_404s(self) -> None:
        response = self.client.get(f'/api/wallet/transactions/{self.other_txn.transaction_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_transaction_404s(self) -> None:
        response = self.client.get('/api/wallet/transactions/TXN99999999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_requires_auth(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get(f'/api/wallet/transactions/{self.txn.transaction_id}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
