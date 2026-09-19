"""Section 13 backend tests.

Covers §43 (notification API: isolation, IDOR, idempotency, filters,
pagination, read/unread) and §44 (event integration: deposit / reward /
withdrawal flows generate exactly one idempotent notification), plus the
wallet transaction search extension (§23).
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.notifications.models import Notification
from apps.notifications.services import notify, notify_event
from apps.wallet.models import Wallet, WalletTransaction
from apps.wallet.services import credit

BT = WalletTransaction.BalanceType
TT = WalletTransaction.TransactionType


class NotificationApiTestBase(APITestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='notif@example.com', password='S3curePass!', phone='+15550900001',
        )
        self.other = User.objects.create_user(
            email='notif-other@example.com', password='S3curePass!', phone='+15550900002',
        )
        Wallet.objects.create(user=self.user)
        Wallet.objects.create(user=self.other)
        self.client.force_authenticate(user=self.user)


class NotificationListTests(NotificationApiTestBase):
    def test_requires_auth(self) -> None:
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_own_newest_first(self) -> None:
        notify(user=self.user, notification_type='SYSTEM', title='First', message='a')
        notify(user=self.user, notification_type='REWARD', title='Second', message='b')
        response = self.client.get('/api/notifications/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data['data']
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['title'], 'Second')  # newest first (§7)
        self.assertIn('unread_count', response.data)
        self.assertEqual(response.data['unread_count'], 2)

    def test_user_isolation(self) -> None:
        notify(user=self.other, notification_type='SYSTEM', title='Not yours', message='x')
        rows = self.client.get('/api/notifications/').data['data']
        self.assertEqual(len(rows), 0)  # other user's rows never leak (§8)

    def test_type_filter(self) -> None:
        notify(user=self.user, notification_type='DEPOSIT', title='Dep', message='a')
        notify(user=self.user, notification_type='REWARD', title='Rew', message='b')
        rows = self.client.get('/api/notifications/?type=reward').data['data']
        self.assertEqual([r['title'] for r in rows], ['Rew'])

    def test_invalid_type_filter_400(self) -> None:
        response = self.client.get('/api/notifications/?type=NOT_A_TYPE')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_is_read_filter(self) -> None:
        row = notify(user=self.user, notification_type='SYSTEM', title='Read me', message='a')
        notify(user=self.user, notification_type='SYSTEM', title='Unread', message='b')
        row.is_read = True
        row.save(update_fields=['is_read'])
        rows = self.client.get('/api/notifications/?is_read=false').data['data']
        self.assertEqual([r['title'] for r in rows], ['Unread'])

    def test_pagination(self) -> None:
        for i in range(7):
            notify(user=self.user, notification_type='SYSTEM', title=f'n{i}', message='m')
        page1 = self.client.get('/api/notifications/?page=1&page_size=3').data
        self.assertEqual(len(page1['data']), 3)
        self.assertEqual(page1['pagination']['pages'], 3)
        page2 = self.client.get('/api/notifications/?page=2&page_size=3').data
        self.assertEqual(len(page2['data']), 3)


class NotificationReadTests(NotificationApiTestBase):
    def setUp(self) -> None:
        super().setUp()
        self.row = notify(
            user=self.user, notification_type='DEPOSIT', title='Dep', message='m',
            related_type='deposit', related_id='DEP00000001',
        )
        self.other_row = notify(user=self.other, notification_type='DEPOSIT', title='X', message='m')

    def test_unread_count(self) -> None:
        data = self.client.get('/api/notifications/unread-count/').data['data']
        self.assertEqual(data['unread_count'], 1)

    def test_detail_own(self) -> None:
        response = self.client.get(f'/api/notifications/{self.row.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['related_type'], 'deposit')

    def test_detail_other_user_404_no_leak(self) -> None:
        # §8/§40: knowing the id must not reveal existence.
        response = self.client.get(f'/api/notifications/{self.other_row.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_read(self) -> None:
        response = self.client.post(f'/api/notifications/{self.row.id}/read/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.row.refresh_from_db()
        self.assertTrue(self.row.is_read)
        self.assertIsNotNone(self.row.read_at)

    def test_mark_read_idempotent(self) -> None:
        self.client.post(f'/api/notifications/{self.row.id}/read/')
        first_read_at = Notification.objects.get(pk=self.row.pk).read_at
        second = self.client.post(f'/api/notifications/{self.row.id}/read/')
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.row.refresh_from_db()
        self.assertEqual(self.row.read_at, first_read_at)  # timestamp not clobbered
        self.assertEqual(Notification.objects.filter(pk=self.row.pk).count(), 1)

    def test_mark_read_other_user_404(self) -> None:
        response = self.client.post(f'/api/notifications/{self.other_row.id}/read/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.other_row.refresh_from_db()
        self.assertFalse(self.other_row.is_read)

    def test_read_all(self) -> None:
        notify(user=self.user, notification_type='SYSTEM', title='Another', message='m')
        response = self.client.post('/api/notifications/read-all/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['marked'], 2)
        self.assertEqual(self.user.notifications.filter(is_read=False).count(), 0)
        # Second call is a no-op, not an error (§5).
        again = self.client.post('/api/notifications/read-all/')
        self.assertEqual(again.data['data']['marked'], 0)


class NotificationServiceTests(NotificationApiTestBase):
    def test_notify_event_idempotent(self) -> None:
        first = notify_event(
            user=self.user, notification_type='REWARD', title='Reward Credited',
            message='m', event_key='reward:REW00000001:credited',
        )
        second = notify_event(
            user=self.user, notification_type='REWARD', title='Reward Credited',
            message='m', event_key='reward:REW00000001:credited',
        )
        self.assertEqual(first.pk, second.pk)  # §19: replay returns same row
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_same_event_key_different_users_allowed(self) -> None:
        a = notify_event(user=self.user, notification_type='REWARD', title='t', message='m',
                         event_key='reward:REW00000002:credited')
        b = notify_event(user=self.other, notification_type='REWARD', title='t', message='m',
                         event_key='reward:REW00000002:credited')
        self.assertNotEqual(a.pk, b.pk)

    def test_plain_event_key_not_reusable(self) -> None:
        notify(user=self.user, notification_type='SYSTEM', title='t', message='m')  # no key
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
        notify_event(user=self.user, notification_type='SYSTEM', title='t2', message='m',
                     event_key='x:1')
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 2)


class EventIntegrationTests(NotificationApiTestBase):
    """§44: existing flows must leave exactly one notification behind."""

    def _credit(self, key: str) -> None:
        credit(
            user=self.user, amount=Decimal('2.50'), balance_type=BT.BONUS,
            transaction_type=TT.VIP_REWARD, reference_type='vip_reward',
            reference_id='REW00000001', description='Daily reward',
            idempotency_key=key,
        )

    def test_reward_credit_then_ledger_notification(self) -> None:
        self._credit('integ-rew-1')
        notify_event(
            user=self.user, notification_type='REWARD',
            title='Reward Credited',
            message='Your daily reward has been credited to your wallet.',
            event_key='reward:REW00000001:credited',
            related_type='vip_reward', related_id='REW00000001',
        )
        # Ledger row + exactly one notification (§20: ledger is the record).
        self.assertEqual(WalletTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(
            Notification.objects.filter(user=self.user, event_key='reward:REW00000001:credited').count(),
            1,
        )
        # Retry the whole cycle (worker replay): nothing duplicates.
        self._credit('integ-rew-1')
        notify_event(
            user=self.user, notification_type='REWARD', title='Reward Credited',
            message='m', event_key='reward:REW00000001:credited',
        )
        self.assertEqual(WalletTransaction.objects.filter(user=self.user).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_no_notification_for_failed_transaction(self) -> None:
        """§18: rollback removes the in-transaction notification."""
        from django.db import transaction

        class Boom(Exception):
            pass

        with self.assertRaises(Boom):
            with transaction.atomic():
                self._credit('integ-fail-1')
                notify_event(
                    user=self.user, notification_type='REWARD', title='Reward Credited',
                    message='m', event_key='reward:REW00000009:credited',
                )
                raise Boom()
        self.assertEqual(WalletTransaction.objects.filter(user=self.user).count(), 0)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 0)


class TransactionSearchApiTests(NotificationApiTestBase):
    """§23: search extension on the existing ledger endpoint."""

    def _seed(self) -> None:
        credit(
            user=self.user, amount=Decimal('10'), balance_type=BT.DEPOSIT,
            transaction_type=TT.DEPOSIT, description='Deposit approval',
            reference_type='deposit', reference_id='DEP00000077',
            idempotency_key='search-1',
        )
        credit(
            user=self.user, amount=Decimal('1'), balance_type=BT.BONUS,
            transaction_type=TT.VIP_REWARD, description='Daily reward',
            reference_type='vip_reward', reference_id='REW00000077',
            idempotency_key='search-2',
        )

    def test_requires_auth(self) -> None:
        self.client.force_authenticate(user=None)
        self.assertEqual(
            self.client.get('/api/wallet/transactions/').status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_search_by_description(self) -> None:
        self._seed()
        rows = self.client.get('/api/wallet/transactions/?search=approval').data['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['type'], 'DEPOSIT')

    def test_search_by_reference_id(self) -> None:
        self._seed()
        rows = self.client.get('/api/wallet/transactions/?search=DEP00000077').data['data']
        self.assertEqual(len(rows), 1)

    def test_search_by_transaction_id_exact(self) -> None:
        self._seed()
        txn_id = WalletTransaction.objects.filter(user=self.user).first().transaction_id
        rows = self.client.get(f'/api/wallet/transactions/?search={txn_id}').data['data']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['transaction_id'], txn_id)

    def test_search_is_user_scoped(self) -> None:
        self._seed()
        credit(
            user=self.other, amount=Decimal('5'), balance_type=BT.DEPOSIT,
            transaction_type=TT.DEPOSIT, description='Deposit approval other',
            idempotency_key='search-3',
        )
        rows = self.client.get('/api/wallet/transactions/?search=approval').data['data']
        self.assertEqual(len(rows), 1)  # only own row matches (§26)

    def test_search_no_injection(self) -> None:
        self._seed()
        response = self.client.get("/api/wallet/transactions/?search=%27%20OR%201%3D1%20--")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 0)  # treated as literal text

    def test_date_range_filter(self) -> None:
        self._seed()
        rows = self.client.get(
            '/api/wallet/transactions/?date_from=2026-01-01&date_to=2026-12-31',
        ).data['data']
        self.assertEqual(len(rows), 2)
        rows = self.client.get(
            '/api/wallet/transactions/?date_from=2030-01-01',
        ).data['data']
        self.assertEqual(len(rows), 0)
