"""Tests for notifications."""

from django.test import TestCase

from apps.accounts.models import User

from .models import Notification


class NotificationTests(TestCase):
    def test_create_and_mark_read(self) -> None:
        user = User.objects.create_user(
            email='n@example.com', password='S3curePass!', phone='+15550008001',
        )
        notification = Notification.objects.create(
            user=user,
            notification_type=Notification.NotificationType.DEPOSIT,
            title='Deposit approved',
            message='Your deposit was credited.',
        )
        self.assertFalse(notification.is_read)
        notification.is_read = True
        notification.save()
        self.assertTrue(Notification.objects.get(pk=notification.pk).is_read)

    def test_unread_index_query(self) -> None:
        user = User.objects.create_user(
            email='n2@example.com', password='S3curePass!', phone='+15550008002',
        )
        Notification.objects.create(user=user, notification_type='SYSTEM', title='Welcome', message='Hi')
        self.assertEqual(Notification.objects.filter(user=user, is_read=False).count(), 1)
