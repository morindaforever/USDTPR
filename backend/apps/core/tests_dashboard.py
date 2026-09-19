"""Tests for the Section 4 read-only dashboard endpoints."""

from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.wallet.models import Wallet


class DashboardApiTestsBase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='dash@example.com', password='S3curePass!', phone='+15550100001', full_name='Dash User'
        )
        self.other = User.objects.create_user(
            email='other@example.com', password='S3curePass!', phone='+15550100002', full_name='Other User'
        )
        # The registration service creates wallets in production; tests
        # bypass it, so create the empty wallets directly.
        Wallet.objects.create(user=self.user)
        Wallet.objects.create(user=self.other)
        self.client.force_authenticate(user=self.user)


class WalletSummaryTests(DashboardApiTestsBase):
    def test_requires_authentication(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/wallet/summary/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_own_wallet_with_zeroed_buckets(self) -> None:
        response = self.client.get('/api/wallet/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])
        data = response.data['data']
        self.assertEqual(Decimal(data['total_balance']), Decimal('0'))
        for key in ('deposit_balance', 'withdrawable_balance', 'pending_balance'):
            self.assertIn(key, data)

    def test_decimal_values_round_trip(self) -> None:
        wallet = self.user.wallet
        wallet.total_balance = Decimal('125.50')
        wallet.deposit_balance = Decimal('50')
        wallet.withdrawable_balance = Decimal('75.50')
        wallet.save()
        data = self.client.get('/api/wallet/summary/').data['data']
        self.assertEqual(Decimal(data['total_balance']), Decimal('125.50'))
        self.assertEqual(Decimal(data['withdrawable_balance']), Decimal('75.50'))

    def test_no_other_users_wallet_leak(self) -> None:
        self.other.wallet.total_balance = Decimal('999')
        self.other.wallet.save()
        data = self.client.get('/api/wallet/summary/?user_id=whatever').data['data']
        self.assertEqual(Decimal(data['total_balance']), Decimal('0'))


class CurrentPlanTests(DashboardApiTestsBase):
    def test_requires_authentication(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/vip/current/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_plan_returns_null_data(self) -> None:
        response = self.client.get('/api/vip/current/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['data'])

    def test_active_plan_snapshot_returned(self) -> None:
        from apps.vip.models import VIPPlan, VIPPurchase

        plan = VIPPlan.objects.create(
            name='VIP 3', plan_number=3, investment_amount=Decimal('50'),
            target_amount=Decimal('75'), daily_rate=Decimal('0.25'),
        )
        VIPPurchase.objects.create(
            user=self.user, vip_plan=plan, status=VIPPurchase.Status.ACTIVE,
            amount_received=Decimal('42'),
        )
        response = self.client.get('/api/vip/current/')
        data = response.data['data']
        self.assertEqual(data['plan_name_snapshot'], 'VIP 3')
        self.assertEqual(Decimal(data['amount_received']), Decimal('42'))
        self.assertEqual(Decimal(data['target_amount']), Decimal('75'))
        self.assertFalse(data['is_welcome_plan'])

    def test_completed_plan_not_returned(self) -> None:
        from apps.vip.models import VIPPlan, VIPPurchase

        plan = VIPPlan.objects.create(
            name='VIP 1', plan_number=1, investment_amount=Decimal('10'),
            target_amount=Decimal('15'), daily_rate=Decimal('0.25'),
        )
        VIPPurchase.objects.create(user=self.user, vip_plan=plan, status=VIPPurchase.Status.COMPLETED)
        response = self.client.get('/api/vip/current/')
        self.assertIsNone(response.data['data'])


class ValuationTests(DashboardApiTestsBase):
    def test_requires_authentication(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/site/valuation/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_demo_rows_are_excluded(self) -> None:
        """Legacy seed rows (is_demo=True) must never reach the API."""
        from apps.core.models import CompanyValuation

        CompanyValuation.objects.create(
            valuation_date=__import__('datetime').date(2026, 1, 1),
            value=Decimal('1000000'), currency='USDT', is_demo=True,
        )
        response = self.client.get('/api/site/valuation/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['data'], [])

    def test_empty_series_handles_gracefully(self) -> None:
        from apps.core.models import CompanyValuation

        CompanyValuation.objects.all().delete()
        response = self.client.get('/api/site/valuation/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['data'], [])
