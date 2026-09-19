"""Tests for core models and endpoints."""

from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .db import HumanIDCounter
from .models import AuditLog, CompanyValuation, SiteSetting


class HealthEndpointTests(APITestCase):
    """GET /api/health/ must always respond ok for unauthenticated users."""

    def test_health_returns_ok(self) -> None:
        response = self.client.get(reverse('core:health'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json(), {'status': 'ok'})

    def test_health_allows_anonymous_access(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse('core:health'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AuditLogTests(APITestCase):
    def test_audit_log_written(self) -> None:
        audit = AuditLog.objects.create(
            action=AuditLog.Action.APPROVE,
            target_type='deposits.Deposit',
            target_id='DEP00000001',
            description='Deposit approved in review.',
        )
        self.assertEqual(str(audit.action), 'APPROVE')
        self.assertEqual(AuditLog.objects.count(), 1)


class SiteSettingTests(APITestCase):
    def test_key_unique(self) -> None:
        SiteSetting.objects.create(key='deposit.min_amount', value='10')
        from django.db import IntegrityError, transaction

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                SiteSetting.objects.create(key='deposit.min_amount', value='20')


class CompanyValuationTests(APITestCase):
    def test_demo_valuation_row(self) -> None:
        valuation = CompanyValuation.objects.create(
            valuation_date='2026-09-16',
            value=Decimal('1250000.00'),
            currency='USDT',
            is_demo=True,
        )
        self.assertTrue(valuation.is_demo)


class HumanIDCounterTests(APITestCase):
    def test_counter_increments_monotonically(self) -> None:
        first = HumanIDCounter.next_value_atomic('TST')
        second = HumanIDCounter.next_value_atomic('TST')
        self.assertEqual(second, first + 1)
