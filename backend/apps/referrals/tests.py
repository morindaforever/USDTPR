"""Section 2 relationship-constraint tests (updated for the Section 9 model).

Commission behavior (calculation, idempotency, concurrency, wallet
accounting) is covered extensively in tests_referrals.py; this module keeps
the original relationship-level coverage.
"""

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.accounts.models import User

from .models import Referral


class ReferralTests(TestCase):
    def setUp(self) -> None:
        self.referrer = User.objects.create_user(
            email='ref@example.com', password='S3curePass!', phone='+15550004001',
        )
        self.referred = User.objects.create_user(
            email='new@example.com', password='S3curePass!', phone='+15550004002',
        )

    def test_relationship_created(self) -> None:
        Referral.objects.create(referrer=self.referrer, referred_user=self.referred)
        self.assertEqual(self.referred.referral_received.referrer, self.referrer)

    def test_duplicate_referral_prevented(self) -> None:
        Referral.objects.create(referrer=self.referrer, referred_user=self.referred)
        other = User.objects.create_user(
            email='x@example.com', password='S3curePass!', phone='+15550004003',
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Referral.objects.create(referrer=other, referred_user=self.referred)

    def test_self_referral_prevented_by_constraint(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Referral.objects.create(referrer=self.referrer, referred_user=self.referrer)

    def test_status_choices_include_blocked(self) -> None:
        referral = Referral.objects.create(
            referrer=self.referrer,
            referred_user=self.referred,
            status=Referral.Status.BLOCKED,
        )
        self.assertEqual(referral.status, 'BLOCKED')
