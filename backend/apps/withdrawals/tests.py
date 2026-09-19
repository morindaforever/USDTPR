"""Tests for Withdrawal and WithdrawalRule.

The simulated-activity model was removed in the production conversion
(§1) — its tests were removed with it.
"""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User
from apps.vip.models import VIPPlan
from apps.wallet.models import Network

from .models import Withdrawal, WithdrawalRule


class WithdrawalTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='w@example.com', password='S3curePass!', phone='+15550006001',
        )
        self.network = Network.objects.create(name='Tron', code='TRX')

    def test_withdrawal_ids_unique(self) -> None:
        other = User.objects.create_user(
            email='w2@example.com', password='S3curePass!', phone='+15550006002',
        )

        def make(user) -> Withdrawal:
            return Withdrawal.objects.create(
                user=user,
                network=self.network,
                requested_amount=Decimal('25'),
                wallet_address='TQ9xxxx',
            )

        first = make(self.user)
        second = make(other)
        self.assertNotEqual(first.withdrawal_id, second.withdrawal_id)
        self.assertRegex(first.withdrawal_id, r'^WDR\d{8,}$')

    def test_network_relationship(self) -> None:
        withdrawal = Withdrawal.objects.create(
            user=self.user, network=self.network, requested_amount=Decimal('5'), wallet_address='TQ1',
        )
        self.assertEqual(withdrawal.network.code, 'TRX')

    def test_preserves_destination_details(self) -> None:
        withdrawal = Withdrawal.objects.create(
            user=self.user, network=self.network,
            requested_amount=Decimal('5'), asset='USDT', wallet_address='TQPRESERVED',
        )
        withdrawal.refresh_from_db()
        self.assertEqual(withdrawal.wallet_address, 'TQPRESERVED')
        self.assertEqual(withdrawal.asset, 'USDT')


class WithdrawalRuleTests(TestCase):
    def test_highest_applicable_rule_selection(self) -> None:
        vip1 = VIPPlan.objects.create(name='VIP 1', plan_number=1, investment_amount=Decimal('10'), target_amount=Decimal('15'), daily_rate=Decimal('0.25'))
        vip3 = VIPPlan.objects.create(name='VIP 3', plan_number=3, investment_amount=Decimal('50'), target_amount=Decimal('75'), daily_rate=Decimal('0.25'))
        vip6 = VIPPlan.objects.create(name='VIP 6', plan_number=6, investment_amount=Decimal('300'), target_amount=Decimal('500'), daily_rate=Decimal('0.25'))
        WithdrawalRule.objects.create(maximum_amount=Decimal('100'), required_vip_plan=vip1)
        WithdrawalRule.objects.create(maximum_amount=Decimal('500'), required_vip_plan=vip3)
        WithdrawalRule.objects.create(maximum_amount=Decimal('800'), required_vip_plan=vip6)

        # Backend can later pick the rule for an amount by ordering:
        rule = (
            WithdrawalRule.objects
            .filter(is_active=True, maximum_amount__gte=Decimal('450'))
            .order_by('maximum_amount')
            .first()
        )
        self.assertEqual(rule.required_vip_plan, vip3)
