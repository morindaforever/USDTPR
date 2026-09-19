"""End-to-end API tests for the authentication system."""

from datetime import timedelta
from decimal import Decimal

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.referrals.models import Referral
from apps.vip.models import VIPPlan, VIPPurchase
from apps.wallet.models import Wallet, WalletTransaction

from .models import LoginActivity, PasswordResetToken, User
from .services import issue_password_reset

STRONG = 'Str0ng!Pass9x'


def auth_header(token: str) -> dict:
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class BaseAuthTest(APITestCase):
    def setUp(self) -> None:
        cache.clear()

    def register(self, email='u@example.com', phone='+15550009001', referral='', **overrides):
        payload = {
            'full_name': 'Test User',
            'email': email,
            'phone': phone,
            'password': STRONG,
            'password_confirm': STRONG,
            'referral_code': referral,
        }
        payload.update(overrides)
        return self.client.post('/api/auth/register/', payload, format='json')

    def login(self, identifier, password=STRONG):
        return self.client.post(
            '/api/auth/login/', {'identifier': identifier, 'password': password}, format='json',
        )

    def token_for(self, identifier='u@example.com') -> str:
        response = self.login(identifier)
        return response.json()['data']['access']


class RegistrationTests(BaseAuthTest):
    def test_valid_registration_creates_user_wallet_ids(self) -> None:
        response = self.register()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertTrue(body['success'])
        user = User.objects.get(email='u@example.com')
        self.assertRegex(user.user_id, r'^USR\d{6}$')
        self.assertRegex(user.referral_code, r'^[A-Z2-9]{7}$')
        self.assertTrue(user.check_password(STRONG))
        wallet = Wallet.objects.get(user=user)
        self.assertEqual(wallet.total_balance, Decimal('0'))
        self.assertEqual(WalletTransaction.objects.count(), 0)

    def test_missing_email_rejected(self) -> None:
        response = self.register(email='')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.json()['errors'])

    def test_missing_phone_rejected(self) -> None:
        response = self.register(phone='')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.json()['errors'])

    def test_invalid_email_format_rejected(self) -> None:
        response = self.register(email='not-an-email')
        self.assertIn('email', response.json()['errors'])

    def test_invalid_phone_format_rejected(self) -> None:
        response = self.register(phone='abc')
        self.assertIn('phone', response.json()['errors'])

    def test_duplicate_email_rejected_case_insensitive(self) -> None:
        self.register(email='Dupe@Example.com', phone='+15550009001')
        response = self.register(email='dupe@example.com', phone='+15550009002')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already exists', response.json()['errors']['email'][0])

    def test_duplicate_phone_rejected(self) -> None:
        self.register(phone='+15550009999')
        response = self.register(email='other@example.com', phone='+15550009999')
        self.assertIn('phone', response.json()['errors'])

    def test_password_mismatch_rejected(self) -> None:
        response = self.register(password_confirm='Different1!')
        self.assertIn('password_confirm', response.json()['errors'])

    def test_weak_password_rejected(self) -> None:
        response = self.register(password='12345678', password_confirm='12345678')
        self.assertIn('password', response.json()['errors'])

    def test_invalid_referral_code_rejected(self) -> None:
        response = self.register(referral='NOPE123')
        self.assertIn('referral_code', response.json()['errors'])
        self.assertIn('Invalid referral code.', response.json()['errors']['referral_code'])

    def test_valid_referral_code_creates_relationship(self) -> None:
        referrer = self.register(email='ref@example.com', phone='+15550009010')
        code = User.objects.get(email='ref@example.com').referral_code
        response = self.register(email='new@example.com', phone='+15550009011', referral=code)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_user = User.objects.get(email='new@example.com')
        self.assertTrue(Referral.objects.filter(referrer__email='ref@example.com', referred_user=new_user).exists())
        self.assertEqual(new_user.referred_by.email, 'ref@example.com')

    def test_self_referral_rejected(self) -> None:
        first = self.register(email='self@example.com', phone='+15550009012')
        code = User.objects.get(email='self@example.com').referral_code
        # A second registration attempt using your own code would need an
        # existing account; the model constraint blocks it structurally.
        with self.assertRaises(Exception):
            Referral.objects.create(
                referrer=User.objects.get(email='self@example.com'),
                referred_user=User.objects.get(email='self@example.com'),
            )

    def test_registration_creates_no_purchases_and_zeroed_wallet(self) -> None:
        """Production conversion (§2): registration grants nothing financial.

        Even if a WELCOME (zero-investment) plan exists, registration must
        NOT create a purchase, credit, or any wallet activity.
        """
        VIPPlan.objects.get_or_create(
            name='WELCOME', plan_number=0,
            defaults={'investment_amount': Decimal('0'), 'target_amount': Decimal('10'), 'daily_rate': Decimal('0.25')},
        )
        self.register()
        user = User.objects.get(email='u@example.com')
        self.assertFalse(VIPPurchase.objects.filter(user=user).exists())
        self.assertEqual(WalletTransaction.objects.count(), 0)
        wallet = user.wallet
        for bucket in (
            'total_balance', 'deposit_balance', 'withdrawable_balance',
            'pending_balance', 'locked_balance', 'bonus_balance',
        ):
            self.assertEqual(getattr(wallet, bucket), 0, bucket)


class LoginTests(BaseAuthTest):
    def setUp(self) -> None:
        super().setUp()
        self.register()

    def test_login_with_email(self) -> None:
        response = self.login('u@example.com')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.json()['data'])

    def test_login_with_phone(self) -> None:
        response = self.login('+15550009001')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_login_with_user_id(self) -> None:
        user_id = User.objects.get(email='u@example.com').user_id
        response = self.login(user_id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_wrong_password_generic_error(self) -> None:
        response = self.login('u@example.com', 'wrong-password')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['message'], 'Invalid credentials.')

    def test_unknown_identifier_generic_error(self) -> None:
        response = self.login('ghost@example.com', 'whatever')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['message'], 'Invalid credentials.')

    def test_suspended_account_denied(self) -> None:
        user = User.objects.get(email='u@example.com')
        user.account_status = User.AccountStatus.SUSPENDED
        user.save()
        response = self.login('u@example.com')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('suspended', response.json()['message'])

    def test_banned_account_gets_generic_error(self) -> None:
        user = User.objects.get(email='u@example.com')
        user.account_status = User.AccountStatus.BANNED
        user.save()
        response = self.login('u@example.com')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.json()['message'], 'Invalid credentials.')

    def test_rate_limiting_blocks_after_five_failures(self) -> None:
        for _ in range(5):
            self.login('u@example.com', 'wrong')
        response = self.login('u@example.com', STRONG)  # even correct password now blocked
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_failed_attempts_recorded(self) -> None:
        self.login('u@example.com', 'wrong')
        user = User.objects.get(email='u@example.com')
        self.assertTrue(LoginActivity.objects.filter(user=user, outcome='FAILED').exists())

    def test_successful_login_recorded(self) -> None:
        self.login('u@example.com')
        user = User.objects.get(email='u@example.com')
        self.assertTrue(LoginActivity.objects.filter(user=user, outcome='SUCCESS').exists())


class ProtectedEndpointTests(BaseAuthTest):
    def setUp(self) -> None:
        super().setUp()
        self.register()

    def test_me_without_token_unauthorized(self) -> None:
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_with_token_ok(self) -> None:
        token = self.token_for()
        response = self.client.get('/api/auth/me/', **auth_header(token))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']['user']
        self.assertEqual(set(data.keys()), {
            'user_id', 'full_name', 'email', 'phone', 'referral_code', 'account_status',
            'is_staff',  # Section 12: presentation-only admin routing flag
        })
        self.assertNotIn('password', data)

    def test_me_with_garbage_token_rejected(self) -> None:
        response = self.client.get('/api/auth/me/', **auth_header('garbage.token.here'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_expired_token_rejected(self) -> None:
        from rest_framework_simplejwt.tokens import AccessToken

        from django.conf import settings

        token = AccessToken()
        token.set_exp(lifetime=timedelta(seconds=-10))
        response = self.client.get('/api/auth/me/', **auth_header(str(token)))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logged_out_token_rejected(self) -> None:
        # Login, then logout (blacklists the refresh cookie and rotation).
        token = self.token_for()
        logout = self.client.post(
            '/api/auth/logout/', {}, format='json', **auth_header(token),
        )
        self.assertEqual(logout.status_code, status.HTTP_200_OK)
        # The access token itself remains valid until expiry (JWT nature),
        # but refresh is blacklisted: cookie refresh must now fail.
        refresh_response = self.client.post('/api/auth/refresh/', {}, format='json')
        self.assertIn(refresh_response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_400_BAD_REQUEST})


class PasswordFlowTests(BaseAuthTest):
    def setUp(self) -> None:
        super().setUp()
        self.register()
        self.user = User.objects.get(email='u@example.com')

    def test_forgot_password_never_reveals_existence(self) -> None:
        known = self.client.post('/api/auth/forgot-password/', {'email': 'u@example.com'}, format='json')
        unknown = self.client.post('/api/auth/forgot-password/', {'email': 'ghost@example.com'}, format='json')
        self.assertEqual(known.json(), unknown.json())
        self.assertTrue(known.json()['success'])

    def test_reset_password_with_valid_token(self) -> None:
        raw = issue_password_reset(self.user)
        response = self.client.post(
            '/api/auth/reset-password/',
            {'token': raw, 'password': 'N3wStr0ng!Pass', 'password_confirm': 'N3wStr0ng!Pass'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('N3wStr0ng!Pass'))

    def test_reset_token_single_use(self) -> None:
        raw = issue_password_reset(self.user)
        first = self.client.post(
            '/api/auth/reset-password/',
            {'token': raw, 'password': 'N3wStr0ng!Pass', 'password_confirm': 'N3wStr0ng!Pass'},
            format='json',
        )
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        second = self.client.post(
            '/api/auth/reset-password/',
            {'token': raw, 'password': 'Again3!Strong', 'password_confirm': 'Again3!Strong'},
            format='json',
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_reset_token_rejected(self) -> None:
        raw = issue_password_reset(self.user)
        row = PasswordResetToken.objects.latest('created_at')
        row.expires_at = timezone.now() - timedelta(seconds=1)
        row.save()
        response = self.client.post(
            '/api/auth/reset-password/',
            {'token': raw, 'password': 'N3wStr0ng!Pass', 'password_confirm': 'N3wStr0ng!Pass'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_requires_current(self) -> None:
        token = self.token_for()
        response = self.client.post(
            '/api/auth/change-password/',
            {'current_password': 'wrong', 'password': 'N3wStr0ng!Pass', 'password_confirm': 'N3wStr0ng!Pass'},
            format='json',
            **auth_header(token),
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('current_password', response.json()['errors'])

    def test_change_password_success(self) -> None:
        token = self.token_for()
        response = self.client.post(
            '/api/auth/change-password/',
            {'current_password': STRONG, 'password': 'N3wStr0ng!Pass', 'password_confirm': 'N3wStr0ng!Pass'},
            format='json',
            **auth_header(token),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('N3wStr0ng!Pass'))

    def test_change_password_mismatch_rejected(self) -> None:
        token = self.token_for()
        response = self.client.post(
            '/api/auth/change-password/',
            {'current_password': STRONG, 'password': 'N3wStr0ng!Pass', 'password_confirm': 'Other3!Pass'},
            format='json',
            **auth_header(token),
        )
        self.assertIn('password_confirm', response.json()['errors'])
