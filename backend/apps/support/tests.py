"""Tests for support models."""

from django.test import TestCase

from apps.accounts.models import User

from .models import SupportConversation, SupportMessage


class SupportTests(TestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='s@example.com', password='S3curePass!', phone='+15550007001',
        )

    def test_conversation_and_messages(self) -> None:
        conversation = SupportConversation.objects.create(user=self.user, subject='Need help')
        SupportMessage.objects.create(conversation=conversation, sender=self.user, message='Hello?')
        admin = User.objects.create_superuser(email='admin@example.com', password='S3curePass!', phone='+15550007002')
        SupportMessage.objects.create(conversation=conversation, sender=admin, message='Hi, how can I help?', is_admin=True)
        self.assertEqual(conversation.messages.count(), 2)
        self.assertEqual(SupportMessage.objects.filter(is_admin=True).count(), 1)

    def test_conversation_ids_human_readable(self) -> None:
        conversation = SupportConversation.objects.create(user=self.user, subject='Q')
        self.assertRegex(conversation.conversation_id, r'^SUP\d{8,}$')
