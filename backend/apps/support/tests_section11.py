"""Section 11 tests: account API + support API.

Covers §70–§77: profile editing (including protected-field rejection),
password change security, activity feed, conversation lifecycle, user
isolation (IDOR), XSS-safe payloads, rate limiting, notifications, and
audit logging.
"""

from datetime import timedelta
from unittest import mock

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import LoginActivity, User
from apps.core.models import AuditLog
from apps.notifications.models import Notification

from .models import SupportConversation, SupportMessage

STRONG = 'S3curePass!'


def auth(client, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')


def make_user(email, phone):
    return User.objects.create_user(
        email=email, password=STRONG, phone=phone, full_name='Test User',
    )


# --------------------------------------------------------------------------- #
# Account API (§70–§71, §77)
# --------------------------------------------------------------------------- #
class AccountProfileTests(APITestCase):
    def setUp(self):
        self.user = make_user('acct@example.com', '+15550008001')
        self.client.force_auth_cookie = None
        auth(self.client, self.user)

    def test_me_and_profile_get(self):
        for url in ('/api/account/me/', '/api/account/profile/'):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['success'])
            self.assertEqual(response.json()['data']['user']['user_id'], self.user.user_id)
            self.assertNotIn('password', response.json()['data']['user'])

    def test_unauthenticated_rejected(self):
        self.client.credentials()
        response = self.client.get('/api/account/me/')
        self.assertEqual(response.status_code, 401)

    def test_profile_update_full_name_and_phone(self):
        response = self.client.patch(
            '/api/account/profile/',
            {'full_name': 'Renamed User', 'phone': '+15550008099'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.full_name, 'Renamed User')
        self.assertEqual(self.user.phone, '+15550008099')

    def test_profile_update_invalid_phone(self):
        response = self.client.patch('/api/account/profile/', {'phone': 'abc'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.json()['errors'])

    def test_profile_update_duplicate_phone(self):
        make_user('other@example.com', '+15550008002')
        response = self.client.patch(
            '/api/account/profile/', {'phone': '+15550008002'}, format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.json()['errors'])

    def test_protected_fields_ignored(self):
        """user_id/status/privilege fields in the payload cannot be applied (§77)."""
        response = self.client.patch(
            '/api/account/profile/',
            {
                'user_id': 'USR000999',
                'account_status': 'BANNED',
                'is_staff': True,
                'referral_code': 'HACKED1',
                'email': 'evil@example.com',
            },
            format='json',
        )
        self.assertEqual(response.status_code, 400)  # nothing valid → 400
        self.user.refresh_from_db()
        self.assertEqual(self.user.user_id, self.user.user_id)  # unchanged
        self.assertEqual(self.user.account_status, 'ACTIVE')
        self.assertFalse(self.user.is_staff)
        self.assertNotEqual(self.user.email, 'evil@example.com')

    def test_profile_update_audit_log(self):
        self.client.patch('/api/account/profile/', {'full_name': 'Audited'}, format='json')
        self.assertTrue(
            AuditLog.objects.filter(
                actor_user=self.user, target_type='account.profile',
            ).exists()
        )


class AccountPasswordTests(APITestCase):
    def setUp(self):
        self.user = make_user('pw@example.com', '+15550008003')
        auth(self.client, self.user)

    def payload(self, current=STRONG, new='N3wStr0ng!Pass', confirm=None):
        return {
            'current_password': current,
            'new_password': new,
            'confirm_password': confirm if confirm is not None else new,
        }

    def test_change_password_success(self):
        response = self.client.post('/api/account/change-password/', self.payload(), format='json')
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('N3wStr0ng!Pass'))

    def test_wrong_current_password(self):
        response = self.client.post(
            '/api/account/change-password/', self.payload(current='wrong'), format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('current_password', response.json()['errors'])

    def test_weak_password_rejected(self):
        response = self.client.post(
            '/api/account/change-password/', self.payload(new='weak', confirm='weak'), format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('new_password', response.json()['errors'])

    def test_mismatched_confirmation(self):
        response = self.client.post(
            '/api/account/change-password/',
            self.payload(new='N3wStr0ng!Pass', confirm='Different1!'),
            format='json',
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('confirm_password', response.json()['errors'])

    def test_same_as_current_rejected(self):
        response = self.client.post(
            '/api/account/change-password/', self.payload(new=STRONG, confirm=STRONG), format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_no_password_material_in_audit(self):
        self.client.post('/api/account/change-password/', self.payload(), format='json')
        row = AuditLog.objects.filter(
            actor_user=self.user, target_type='account.password',
        ).latest('created_at')
        blob = f'{row.description} {row.target_type} {row.action}'
        self.assertNotIn(STRONG, blob)
        self.assertNotIn('N3wStr0ng!Pass', blob)

    def test_refresh_tokens_blacklisted_after_change(self):
        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        self.assertTrue(
            OutstandingToken.objects.filter(jti=refresh['jti']).exists()
        )
        self.client.post('/api/account/change-password/', self.payload(), format='json')
        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

        token = OutstandingToken.objects.get(jti=refresh['jti'])
        self.assertTrue(BlacklistedToken.objects.filter(token=token).exists())


class AccountActivityTests(APITestCase):
    def setUp(self):
        self.user = make_user('act@example.com', '+15550008004')
        auth(self.client, self.user)

    def test_activity_contains_login(self):
        LoginActivity.objects.create(
            user=self.user, outcome=LoginActivity.Outcome.SUCCESS, detail='login',
        )
        response = self.client.get('/api/account/activity/')
        self.assertEqual(response.status_code, 200)
        types = [e['type'] for e in response.json()['data']['results']]
        self.assertIn('login', types)

    def test_activity_user_isolation(self):
        other = make_user('act2@example.com', '+15550008005')
        LoginActivity.objects.create(
            user=other, outcome=LoginActivity.Outcome.SUCCESS, detail='login',
        )
        response = self.client.get('/api/account/activity/')
        types = [e['type'] for e in response.json()['data']['results']]
        self.assertNotIn('login', types)  # only the requester's rows


# --------------------------------------------------------------------------- #
# Support API (§72–§76)
# --------------------------------------------------------------------------- #
class SupportConversationTests(APITestCase):
    def setUp(self):
        self.user = make_user('sup@example.com', '+15550008006')
        self.other = make_user('sup2@example.com', '+15550008007')
        self.admin = User.objects.create_superuser(
            email='admin@example.com', password=STRONG, phone='+15550008008',
        )
        auth(self.client, self.user)

    def create(self, subject='Withdrawal issue', message='I need help.'):
        return self.client.post(
            '/api/support/conversations/', {'subject': subject, 'message': message},
            format='json',
        )

    def test_create_conversation(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        data = response.json()['data']
        self.assertEqual(data['subject'], 'Withdrawal issue')
        self.assertEqual(data['status'], 'OPEN')
        self.assertEqual(len(data['messages']), 1)
        conversation = SupportConversation.objects.get(conversation_id=data['conversation_id'])
        self.assertEqual(conversation.user, self.user)

    def test_empty_subject_rejected(self):
        response = self.create(subject='   ')
        self.assertEqual(response.status_code, 400)
        self.assertIn('subject', response.json()['errors'])

    def test_empty_message_rejected(self):
        response = self.create(message='')
        self.assertEqual(response.status_code, 400)
        self.assertIn('message', response.json()['errors'])

    def test_oversized_message_rejected(self):
        response = self.create(message='x' * 5001)
        self.assertEqual(response.status_code, 400)

    def test_list_only_own_conversations(self):
        self.create()
        SupportConversation.objects.create(user=self.other, subject='Other person')
        response = self.client.get('/api/support/conversations/')
        subjects = [row['subject'] for row in response.json()['data']]
        self.assertIn('Withdrawal issue', subjects)
        self.assertNotIn('Other person', subjects)

    def test_status_filter(self):
        self.create()
        SupportConversation.objects.create(user=self.user, subject='Resolved one', status='RESOLVED')
        response = self.client.get('/api/support/conversations/?status=RESOLVED')
        subjects = [row['subject'] for row in response.json()['data']]
        self.assertEqual(subjects, ['Resolved one'])

    def test_detail_owner_only(self):
        created = self.create().json()['data']
        response = self.client.get(f"/api/support/conversations/{created['conversation_id']}/")
        self.assertEqual(response.status_code, 200)

        auth(self.client, self.other)
        foreign = self.client.get(f"/api/support/conversations/{created['conversation_id']}/")
        self.assertEqual(foreign.status_code, 404)

    def test_send_message_appends_and_orders(self):
        created = self.create().json()['data']
        cid = created['conversation_id']
        second = self.client.post(f'/api/support/conversations/{cid}/messages/',
                                  {'message': 'Second message'}, format='json')
        self.assertEqual(second.status_code, 201)
        messages = second.json()['data']['messages']
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['message'], 'I need help.')
        self.assertEqual(messages[1]['message'], 'Second message')
        self.assertEqual(messages[0]['sender_type'], 'user')

    def test_user_reply_sets_in_progress(self):
        conversation = SupportConversation.objects.create(
            user=self.user, subject='Waiting', status=SupportConversation.Status.RESOLVED,
        )
        response = self.client.post(
            f'/api/support/conversations/{conversation.conversation_id}/messages/',
            {'message': 'Follow-up question'}, format='json',
        )
        self.assertEqual(response.status_code, 201)
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, SupportConversation.Status.IN_PROGRESS)

    def test_closed_conversation_rejects_messages(self):
        conversation = SupportConversation.objects.create(
            user=self.user, subject='Done', status=SupportConversation.Status.CLOSED,
        )
        response = self.client.post(
            f'/api/support/conversations/{conversation.conversation_id}/messages/',
            {'message': 'Hello?'}, format='json',
        )
        self.assertEqual(response.status_code, 409)

    def test_close_conversation(self):
        created = self.create().json()['data']
        response = self.client.post(f"/api/support/conversations/{created['conversation_id']}/close/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data']['status'], 'CLOSED')

    def test_double_close_idempotent(self):
        created = self.create().json()['data']
        cid = created['conversation_id']
        first = self.client.post(f'/api/support/conversations/{cid}/close/')
        second = self.client.post(f'/api/support/conversations/{cid}/close/')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertIn('already', second.json()['message'])

    def test_reopen_closed_conversation(self):
        conversation = SupportConversation.objects.create(
            user=self.user, subject='Reopen me', status=SupportConversation.Status.CLOSED,
        )
        response = self.client.post(
            f'/api/support/conversations/{conversation.conversation_id}/reopen/',
        )
        self.assertEqual(response.status_code, 200)
        conversation.refresh_from_db()
        self.assertEqual(conversation.status, SupportConversation.Status.IN_PROGRESS)

    def test_reopen_open_conversation_rejected(self):
        created = self.create().json()['data']
        response = self.client.post(f"/api/support/conversations/{created['conversation_id']}/reopen/")
        self.assertEqual(response.status_code, 409)

    def test_pagination_shape(self):
        for i in range(3):
            self.create(subject=f'Subject {i}')
        response = self.client.get('/api/support/conversations/')
        body = response.json()
        self.assertIn('pagination', body)
        self.assertEqual(body['pagination']['count'], 3)

    def test_rate_limit_on_creation(self):
        for i in range(5):
            response = self.create(subject=f'Subject {i}')
            self.assertEqual(response.status_code, 201)
        response = self.create(subject='One too many')
        self.assertEqual(response.status_code, 429)

    def test_unsafe_link_scheme_rejected(self):
        response = self.create(message='click javascript:alert(1) please')
        self.assertEqual(response.status_code, 400)

    def test_xss_payload_stored_as_text(self):
        """Script payloads are stored as inert text (rendered escaped; §75)."""
        payload = '<script>alert("xss")</script>'
        response = self.create(message=payload)
        self.assertEqual(response.status_code, 201)
        self.assertIn(payload, response.json()['data']['messages'][0]['message'])

    def test_audit_rows_written(self):
        created = self.create().json()['data']
        cid = created['conversation_id']
        self.client.post(f'/api/support/conversations/{cid}/close/')
        actions = list(
            AuditLog.objects.filter(
                actor_user=self.user, target_type='support.conversation',
            ).values_list('description', flat=True)
        )
        self.assertTrue(any('created' in a for a in actions))
        self.assertTrue(any('closed' in a for a in actions))


class SupportNotificationTests(APITestCase):
    def setUp(self):
        self.user = make_user('notif@example.com', '+15550008009')
        self.admin = User.objects.create_superuser(
            email='admin@example.com', password=STRONG, phone='+15550008010',
        )
        self.conversation = SupportConversation.objects.create(user=self.user, subject='Notify me')
        SupportMessage.objects.create(conversation=self.conversation, sender=self.user, message='Hi')

    def test_staff_reply_creates_notification(self):
        before = Notification.objects.filter(user=self.user).count()
        services = __import__('apps.support.services', fromlist=['services'])
        services.send_message(self.admin, self.conversation, 'Support reply here')
        after = Notification.objects.filter(user=self.user).count()
        self.assertEqual(after, before + 1)
        notification = Notification.objects.filter(user=self.user).latest('created_at')
        self.assertEqual(notification.notification_type, 'SUPPORT')
        self.assertIn('Notify me', notification.message)

    def test_user_reply_does_not_self_notify(self):
        before = Notification.objects.filter(user=self.user).count()
        services = __import__('apps.support.services', fromlist=['services'])
        services.send_message(self.user, self.conversation, 'Adding detail')
        self.assertEqual(Notification.objects.filter(user=self.user).count(), before)

    def test_no_duplicate_notification_per_message(self):
        services = __import__('apps.support.services', fromlist=['services'])
        services.send_message(self.admin, self.conversation, 'Reply one')
        services.send_message(self.admin, self.conversation, 'Reply two')
        titles = Notification.objects.filter(user=self.user, title='New support reply')
        self.assertEqual(titles.count(), 2)  # one per staff message, never duplicated


class SupportRateLimitMessageTests(APITestCase):
    def setUp(self):
        self.user = make_user('rate@example.com', '+15550008011')
        self.conversation = SupportConversation.objects.create(user=self.user, subject='Rate')
        auth(self.client, self.user)

    def test_message_rate_limit(self):
        # Limit is 30/hour: 30 pass, the 31st is blocked (§76).
        for _ in range(30):
            response = self.client.post(
                f'/api/support/conversations/{self.conversation.conversation_id}/messages/',
                {'message': 'spam'}, format='json',
            )
            self.assertEqual(response.status_code, 201)
        blocked = self.client.post(
            f'/api/support/conversations/{self.conversation.conversation_id}/messages/',
            {'message': 'one more'}, format='json',
        )
        self.assertEqual(blocked.status_code, 429)
