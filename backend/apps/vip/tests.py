"""Tests for VIP models: plans, snapshot semantics, duplicate-reward guard."""

from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User

from .models import VIPPlan, VIPPurchase, VIPReward


class VIPModelTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='v@example.com', password='S3curePass!', phone='+15550003001',
        )
        self.plan = VIPPlan.objects.create(
            name='VIP 1',
            plan_number=1,
            investment_amount=Decimal('10'),
            target_amount=Decimal('15'),
            daily_rate=Decimal('0.25'),
        )

    def test_plans_exist(self) -> None:
        self.assertTrue(VIPPlan.objects.filter(name='VIP 1').exists())

    def test_purchase_stores_plan_snapshot(self) -> None:
        purchase = VIPPurchase.objects.create(user=self.user, vip_plan=self.plan)
        self.assertEqual(purchase.plan_name_snapshot, 'VIP 1')
        self.assertEqual(purchase.investment_amount, Decimal('10'))
        self.assertEqual(purchase.target_amount, Decimal('15'))
        self.assertEqual(purchase.daily_rate_snapshot, Decimal('0.25'))

    def test_snapshot_unchanged_when_plan_edited(self) -> None:
        purchase = VIPPurchase.objects.create(user=self.user, vip_plan=self.plan)
        self.plan.investment_amount = Decimal('999')
        self.plan.save()
        purchase.refresh_from_db()
        self.assertEqual(purchase.investment_amount, Decimal('10'))

    def test_duplicate_reward_for_same_date_rejected(self) -> None:
        purchase = VIPPurchase.objects.create(user=self.user, vip_plan=self.plan)
        VIPReward.objects.create(
            user=self.user,
            vip_purchase=purchase,
            reward_date=date(2026, 9, 16),
            calculated_amount=Decimal('2.5'),
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VIPReward.objects.create(
                    user=self.user,
                    vip_purchase=purchase,
                    reward_date=date(2026, 9, 16),
                    calculated_amount=Decimal('2.5'),
                )

    def test_same_date_different_purchase_allowed(self) -> None:
        first = VIPPurchase.objects.create(user=self.user, vip_plan=self.plan)
        second = VIPPurchase.objects.create(user=self.user, vip_plan=self.plan)
        VIPReward.objects.create(user=self.user, vip_purchase=first, reward_date=date(2026, 9, 16), calculated_amount=Decimal('1'))
        VIPReward.objects.create(user=self.user, vip_purchase=second, reward_date=date(2026, 9, 16), calculated_amount=Decimal('1'))
        self.assertEqual(VIPReward.objects.count(), 2)
