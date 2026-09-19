"""Tests for the custom User model."""

from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import User


class UserModelTests(TestCase):
    def _create(self, email, phone, **kwargs) -> User:
        return User.objects.create_user(email=email, password='S3curePass!', phone=phone, **kwargs)

    def test_create_user_hashes_password(self) -> None:
        user = self._create('a@example.com', '+15550000001')
        self.assertNotEqual(user.password, 'S3curePass!')
        self.assertTrue(user.check_password('S3curePass!'))

    def test_user_id_human_format_and_unique(self) -> None:
        first = self._create('a@example.com', '+15550000001')
        second = self._create('b@example.com', '+15550000002')
        self.assertRegex(first.user_id, r'^USR\d{6,}$')
        self.assertNotEqual(first.user_id, second.user_id)

    def test_email_is_unique_case_insensitive(self) -> None:
        self._create('Alpha@Example.com', '+15550000001')
        # The manager normalizes emails to lowercase, so full_clean's unique
        # check catches the case-insensitive duplicate before the DB does.
        with self.assertRaises(ValidationError):
            self._create('alpha@example.com', '+15550000002')

    def test_phone_is_unique(self) -> None:
        self._create('a@example.com', '+15550000001')
        with self.assertRaises(ValidationError):
            self._create('b@example.com', '+15550000001')

    def test_referral_code_unique_between_users(self) -> None:
        first = self._create('a@example.com', '+15550000001')
        second = self._create('b@example.com', '+15550000002')
        self.assertNotEqual(first.referral_code, second.referral_code)

    def test_referred_by_self_rejected_at_model_level(self) -> None:
        user = self._create('a@example.com', '+15550000001')
        user.referred_by = user
        with self.assertRaises(ValueError):
            user.clean()

    def test_soft_status_choices(self) -> None:
        user = self._create('a@example.com', '+15550000001', account_status=User.AccountStatus.SUSPENDED)
        self.assertEqual(user.account_status, User.AccountStatus.SUSPENDED)
