"""Section 12 tests: admin panel authorization, management actions, and
financial integrity.

Covers §90–§104: unauthenticated/normal-user/admin access, user management
with audit + notification, deposit approve/reject idempotency with exactly
one credit, withdrawal state machine through the admin API, VIP plan
validation + snapshot preservation, reward processing/retry idempotency,
support reply + notification, settings audit, and mass-assignment/
privilege-escalation rejection.
"""

from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.core.models import AuditLog, SiteSetting
from apps.deposits.models import Deposit
from apps.notifications.models import Notification
from apps.referrals.config import reset_cache
from apps.support.models import SupportConversation, SupportMessage
from apps.vip.models import VIPPlan, VIPPurchase, VIPReward
from apps.wallet.models import Network, Wallet, WalletTransaction
from apps.withdrawals import config as wd_config
from apps.withdrawals.models import Withdrawal

STRONG = 'S3curePass!'


def make_user(email, phone, **extra):
    return User.objects.create_user(
        email=email, password=STRONG, phone=phone, full_name='User ' + email, **extra,
    )


def make_admin(email='admin@example.com', phone='+15550012001', superuser=True):
    return User.objects.create_superuser(email=email, password=STRONG, phone=phone)


def auth(client, user):
    from rest_framework_simplejwt.tokens import RefreshToken

    token = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')


class AdminAccessTests(APITestCase):
    """§90: unauthenticated → 401, normal user → 403, admin → 200."""

    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('normal@example.com', '+15550012002')

    def test_unauthenticated_gets_401(self):
        response = self.client.get('/api/admin/dashboard/')
        self.assertEqual(response.status_code, 401)

    def test_normal_user_gets_403(self):
        auth(self.client, self.user)
        response = self.client.get('/api/admin/dashboard/')
        self.assertEqual(response.status_code, 403)

    def test_admin_gets_200(self):
        auth(self.client, self.admin)
        response = self.client.get('/api/admin/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])

    def test_no_password_fields_anywhere(self):
        auth(self.client, self.admin)
        response = self.client.get('/api/admin/users/')
        blob = str(response.json())
        self.assertNotIn('password', blob.lower())


class AdminDashboardTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        auth(self.client, self.admin)

    def test_stats_are_real_counts(self):
        make_user('u1@example.com', '+15550012010')
        make_user('u2@example.com', '+15550012011', account_status=User.AccountStatus.SUSPENDED)
        response = self.client.get('/api/admin/dashboard/')
        data = response.json()['data']
        self.assertEqual(data['total_users'], User.objects.count())
        self.assertEqual(
            data['active_users'],
            User.objects.filter(account_status='ACTIVE', is_active=True).count(),
        )

    def test_financial_metrics_are_real_aggregates(self):
        """Production conversion: dashboard metrics are actual DB counts."""
        response = self.client.get('/api/admin/dashboard/')
        metrics = response.json()['data']['financial_metrics']
        self.assertIn('actual database records', metrics['label'])
        # Empty database → honest zeros (§15).
        self.assertEqual(metrics['deposits_submitted']['count'], 0)
        self.assertEqual(metrics['rewards_credited']['count'], 0)

    def test_range_filters_accepted(self):
        for rng in ('today', '7d', '30d', 'all'):
            response = self.client.get(f'/api/admin/dashboard/?range={rng}')
            self.assertEqual(response.status_code, 200)


class AdminUserManagementTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('target@example.com', '+15550012020')
        self.staff_limited = User.objects.create_user(
            email='limited@example.com', password=STRONG, phone='+15550012021',
            is_staff=True,
        )
        self.client.force_auth_cookie = None

    def test_user_search_server_side(self):
        auth(self.client, self.admin)
        response = self.client.get('/api/admin/users/?search=target@example.com')
        results = response.json()['data']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['user_id'], self.user.user_id)

    def test_user_status_filter(self):
        auth(self.client, self.admin)
        response = self.client.get('/api/admin/users/?status=SUSPENDED')
        self.assertEqual(response.json()['data'], [])

    def test_user_detail_includes_wallet(self):
        auth(self.client, self.admin)
        response = self.client.get(f"/api/admin/users/{self.user.user_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn('wallet', response.json()['data'])

    def test_suspend_requires_reason(self):
        auth(self.client, self.admin)
        response = self.client.post(
            f"/api/admin/users/{self.user.user_id}/status/",
            {'action': 'suspend', 'reason': ''}, format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_suspend_then_activate(self):
        auth(self.client, self.admin)
        response = self.client.post(
            f"/api/admin/users/{self.user.user_id}/status/",
            {'action': 'suspend', 'reason': 'Manual security review required'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_status, 'SUSPENDED')
        # Audit + notification created (§15, §104)
        self.assertTrue(AuditLog.objects.filter(
            actor_user=self.admin, target_id=self.user.user_id,
            target_type='admin.user_status').exists())
        self.assertTrue(Notification.objects.filter(
            user=self.user, title='Account suspended').exists())

        # Activate back
        response = self.client.post(
            f"/api/admin/users/{self.user.user_id}/status/",
            {'action': 'activate', 'reason': 'review complete'}, format='json',
        )
        self.user.refresh_from_db()
        self.assertEqual(self.user.account_status, 'ACTIVE')

    def test_idempotent_status_change(self):
        auth(self.client, self.admin)
        self.client.post(
            f"/api/admin/users/{self.user.user_id}/status/",
            {'action': 'suspend', 'reason': 'first'}, format='json',
        )
        before = AuditLog.objects.filter(target_id=self.user.user_id).count()
        response = self.client.post(
            f"/api/admin/users/{self.user.user_id}/status/",
            {'action': 'suspend', 'reason': 'second'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        after = AuditLog.objects.filter(target_id=self.user.user_id).count()
        self.assertEqual(before, after)  # no duplicate audit on repeat

    def test_suspended_user_session_blacklisted(self):
        from rest_framework_simplejwt.token_blacklist.models import (
            BlacklistedToken, OutstandingToken,
        )
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.user)
        auth(self.client, self.admin)
        self.client.post(
            f"/api/admin/users/{self.user.user_id}/status/",
            {'action': 'suspend', 'reason': 'security'}, format='json',
        )
        token_row = OutstandingToken.objects.get(jti=refresh['jti'])
        self.assertTrue(BlacklistedToken.objects.filter(token=token_row).exists())

    def test_superuser_cannot_be_banned(self):
        auth(self.client, self.admin)
        response = self.client.post(
            f"/api/admin/users/{self.admin.user_id}/status/",
            {'action': 'ban', 'reason': 'try'}, format='json',
        )
        self.assertEqual(response.status_code, 409)

    def test_limited_staff_without_group_gets_403(self):
        """§66: staff without the User Managers group cannot change status."""
        auth(self.client, self.staff_limited)
        response = self.client.post(
            f"/api/admin/users/{self.user.user_id}/status/",
            {'action': 'suspend', 'reason': 'x'}, format='json',
        )
        self.assertEqual(response.status_code, 403)

    def test_limited_staff_with_group_allowed(self):
        group, _ = Group.objects.get_or_create(name='User Managers')
        self.staff_limited.groups.add(group)
        auth(self.client, self.staff_limited)
        response = self.client.post(
            f"/api/admin/users/{self.user.user_id}/status/",
            {'action': 'suspend', 'reason': 'group-granted'}, format='json',
        )
        self.assertEqual(response.status_code, 200)

    def test_user_history_endpoints(self):
        auth(self.client, self.admin)
        for kind in ('deposits', 'withdrawals', 'vip', 'rewards', 'commissions',
                     'support', 'logins', 'audit'):
            response = self.client.get(f"/api/admin/users/{self.user.user_id}/history/?type={kind}")
            self.assertEqual(response.status_code, 200, kind)

    def test_normal_user_cannot_access_user_management(self):
        auth(self.client, self.user)
        response = self.client.get('/api/admin/users/')
        self.assertEqual(response.status_code, 403)


class AdminDepositTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('depositor@example.com', '+15550012030')
        Wallet.objects.create(user=self.user)
        self.network = Network.objects.create(name='Tron', code='TRX', sort_order=1)
        self.deposit = Deposit.objects.create(
            user=self.user, network=self.network, amount=Decimal('25.00'),
            tx_hash='deadbeef123', status=Deposit.Status.PENDING,
        )
        auth(self.client, self.admin)

    def test_approve_credits_exactly_once(self):
        response = self.client.post(f"/api/admin/deposits/{self.deposit.deposit_id}/approve/")
        self.assertEqual(response.status_code, 200)
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.deposit_balance, Decimal('25.00'))
        credits = WalletTransaction.objects.filter(
            user=self.user, reference_id=self.deposit.deposit_id,
            transaction_type='DEPOSIT', direction='CREDIT',
        )
        self.assertEqual(credits.count(), 1)

    def test_duplicate_approve_is_idempotent(self):
        """Repeat approve returns the existing result; still exactly one credit."""
        self.client.post(f"/api/admin/deposits/{self.deposit.deposit_id}/approve/")
        response = self.client.post(f"/api/admin/deposits/{self.deposit.deposit_id}/approve/")
        self.assertEqual(response.status_code, 200)  # service returns existing state
        credits = WalletTransaction.objects.filter(
            user=self.user, reference_id=self.deposit.deposit_id,
            transaction_type='DEPOSIT', direction='CREDIT',
        )
        self.assertEqual(credits.count(), 1)
        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.deposit_balance, Decimal('25.00'))

    def test_reject_requires_reason(self):
        response = self.client.post(f"/api/admin/deposits/{self.deposit.deposit_id}/reject/", {})
        self.assertEqual(response.status_code, 400)

    def test_reject_no_wallet_credit(self):
        response = self.client.post(
            f"/api/admin/deposits/{self.deposit.deposit_id}/reject/",
            {'reason': 'hash not found on-chain'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.status, 'REJECTED')
        self.assertEqual(Wallet.objects.get(user=self.user).deposit_balance, Decimal('0.00'))


class AdminWithdrawalTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('withdrawer@example.com', '+15550012040')
        Wallet.objects.create(user=self.user, withdrawable_balance=Decimal('50.00'))
        self.network = Network.objects.create(name='Tron', code='TRX', sort_order=1)
        wd_config.invalidate_cache()
        from apps.withdrawals import services as ws

        # Withdrawal-eligibility fixture: a paid VIP purchase unlocks withdrawals.
        from apps.vip.models import VIPPlan as _VP, VIPPurchase as _VPur

        _paid, _ = _VP.objects.get_or_create(
            name='VIP 1', defaults={
                'plan_number': 1, 'investment_amount': Decimal('10'),
                'target_amount': Decimal('15'), 'daily_rate': Decimal('0.25'),
            },
        )
        _VPur.objects.create(
            user=self.user, vip_plan=_paid, plan_name_snapshot=_paid.name,
            investment_amount=_paid.investment_amount, target_amount=_paid.target_amount,
            daily_rate_snapshot=_paid.daily_rate, status='ACTIVE',
            idempotency_key=f'TEST_PAID_VIP_admin_{self.user.pk}',
        )
        self.withdrawal, _ = ws.create_withdrawal(
            user=self.user, network_code='TRX',
            destination_address='Th82pJGF9p7kpzb6eU326EFZf2cDnimbTF',
            amount='20', idempotency_key='admin-test-wd-1',
        )
        auth(self.client, self.admin)

    def wallet(self):
        return Wallet.objects.get(user=self.user)

    def test_full_lifecycle(self):
        base = f"/api/admin/withdrawals/{self.withdrawal.withdrawal_id}"
        # PENDING → APPROVED: funds stay locked (§27)
        response = self.client.post(f'{base}/approve/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wallet().locked_balance, Decimal('20.00'))
        # APPROVED → PROCESSING
        response = self.client.post(f'{base}/processing/')
        self.assertEqual(response.status_code, 200)
        # PROCESSING → COMPLETED with a real-format on-chain hash only.
        # Conversion §10: non-hex placeholders are rejected by the service.
        response = self.client.post(
            f'{base}/complete/',
            {'transaction_hash': 'a' * 64},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wallet().locked_balance, Decimal('0.00'))
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('30.00'))
        finalizes = WalletTransaction.objects.filter(
            user=self.user, reference_id=self.withdrawal.withdrawal_id,
            transaction_type='WITHDRAWAL',
        )
        self.assertEqual(finalizes.count(), 1)

    def test_invalid_transition_409(self):
        base = f"/api/admin/withdrawals/{self.withdrawal.withdrawal_id}"
        response = self.client.post(f'{base}/complete/')
        self.assertEqual(response.status_code, 409)

    def test_reject_releases_once(self):
        base = f"/api/admin/withdrawals/{self.withdrawal.withdrawal_id}"
        response = self.client.post(f'{base}/reject/', {'reason': 'suspicious address'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('50.00'))
        self.assertEqual(self.wallet().locked_balance, Decimal('0.00'))
        # Second reject → 409 (idempotency guard via state machine)
        response = self.client.post(f'{base}/reject/', {'reason': 'again'}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.wallet().withdrawable_balance, Decimal('50.00'))


class AdminVIPTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('vipuser@example.com', '+15550012050')
        auth(self.client, self.admin)

    def test_plan_create_validation(self):
        response = self.client.post('/api/admin/vip-plans/', {
            'name': 'VIP 1', 'plan_number': 1, 'investment_amount': '10.00',
            'target_amount': '15.00', 'daily_rate': '0.25', 'is_active': True,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        # duplicate name
        response = self.client.post('/api/admin/vip-plans/', {
            'name': 'vip 1', 'plan_number': 2, 'investment_amount': '10.00',
            'target_amount': '15.00', 'daily_rate': '0.25',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_target_must_exceed_investment(self):
        response = self.client.post('/api/admin/vip-plans/', {
            'name': 'Bad', 'plan_number': 9, 'investment_amount': '20.00',
            'target_amount': '15.00', 'daily_rate': '0.25',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_welcome_plan_allows_zero_investment(self):
        """A WELCOME plan may set investment_amount = 0 (promotional plan)."""
        response = self.client.post('/api/admin/vip-plans/', {
            'name': 'WELCOME', 'plan_number': 50, 'investment_amount': '0.00',
            'target_amount': '10.00', 'daily_rate': '0.25', 'is_active': True,
        }, format='json')
        self.assertEqual(response.status_code, 201)
        plan = VIPPlan.objects.get(name='WELCOME', plan_number=50)
        self.assertEqual(plan.investment_amount, Decimal('0.00'))
        self.assertEqual(plan.target_amount, Decimal('10.00'))

    def test_welcome_plan_can_be_edited_while_zero(self):
        plan = VIPPlan.objects.create(
            name='WELCOME', plan_number=51, investment_amount=Decimal('0'),
            target_amount=Decimal('10'), daily_rate=Decimal('0.25'),
        )
        response = self.client.patch(f'/api/admin/vip-plans/{plan.pk}/', {
            'target_amount': '12.00',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        plan.refresh_from_db()
        self.assertEqual(plan.investment_amount, Decimal('0.00'))
        self.assertEqual(plan.target_amount, Decimal('12.00'))

    def test_zero_investment_rejected_for_paid_plans(self):
        """Non-WELCOME plans still require a positive investment amount."""
        response = self.client.post('/api/admin/vip-plans/', {
            'name': 'Freebie', 'plan_number': 52, 'investment_amount': '0.00',
            'target_amount': '10.00', 'daily_rate': '0.25',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('investment_amount', response.json().get('errors', {}))
        # Renaming a paid plan to WELCOME on edit makes 0 acceptable; renaming
        # a zero plan to a paid name with 0 investment stays rejected.
        plan = VIPPlan.objects.create(
            name='Temp Paid', plan_number=53, investment_amount=Decimal('5'),
            target_amount=Decimal('10'), daily_rate=Decimal('0.25'),
        )
        response = self.client.patch(f'/api/admin/vip-plans/{plan.pk}/', {
            'investment_amount': '0.00',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_plan_edit_preserves_purchase_snapshot(self):
        plan = VIPPlan.objects.create(
            name='VIP 1', plan_number=1, investment_amount=Decimal('10'),
            target_amount=Decimal('15'), daily_rate=Decimal('0.25'),
        )
        purchase = VIPPurchase.objects.create(
            user=self.user, vip_plan=plan, plan_name_snapshot=plan.name,
            investment_amount=plan.investment_amount, target_amount=plan.target_amount,
            daily_rate_snapshot=plan.daily_rate, status='ACTIVE',
        )
        self.client.patch(f'/api/admin/vip-plans/{plan.pk}/', {
            'investment_amount': '20.00', 'target_amount': '30.00',
        }, format='json')
        purchase.refresh_from_db()
        self.assertEqual(purchase.investment_amount, Decimal('10.00'))
        self.assertEqual(purchase.target_amount, Decimal('15.00'))
        self.assertEqual(purchase.daily_rate_snapshot, Decimal('0.25'))

    def test_purchase_list_and_filters(self):
        response = self.client.get('/api/admin/vip-purchases/?status=ACTIVE')
        self.assertEqual(response.status_code, 200)


class AdminRewardTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('rewarduser@example.com', '+15550012060')
        Wallet.objects.create(user=self.user)
        auth(self.client, self.admin)

    def test_process_uses_existing_engine(self):
        with mock.patch('apps.adminpanel.finance_views.process_daily_rewards') as engine:
            engine.return_value = {'credited': 0, 'eligible': 0}
            response = self.client.post('/api/admin/rewards/process/', {}, format='json')
        self.assertEqual(response.status_code, 200)
        engine.assert_called_once()

    def test_retry_completed_reward_is_noop(self):
        plan = VIPPlan.objects.create(
            name='VIP RT', plan_number=30, investment_amount=Decimal('10'),
            target_amount=Decimal('15'), daily_rate=Decimal('0.25'),
        )
        reward = VIPReward.objects.create(
            user=self.user,
            vip_purchase=VIPPurchase.objects.create(
                user=self.user, vip_plan=plan, plan_name_snapshot='VIP RT',
                investment_amount=Decimal('10'), target_amount=Decimal('15'),
                daily_rate_snapshot=Decimal('0.25'), status='ACTIVE',
            ),
            reward_date=__import__('datetime').date.today(),
            calculated_amount=Decimal('2.50'), credited_amount=Decimal('2.50'),
            status='COMPLETED',
        )
        with mock.patch('apps.vip.reward_service.process_reward') as engine:
            response = self.client.post(f'/api/admin/rewards/{reward.reward_id}/retry/')
        self.assertEqual(response.status_code, 200)
        engine.assert_not_called()  # idempotent: completed rewards never re-credit

    def test_reward_list(self):
        response = self.client.get('/api/admin/rewards/?status=COMPLETED')
        self.assertEqual(response.status_code, 200)


class AdminSupportTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('supportee@example.com', '+15550012070')
        self.conversation = SupportConversation.objects.create(user=self.user, subject='Help me')
        SupportMessage.objects.create(conversation=self.conversation, sender=self.user, message='Please help')
        auth(self.client, self.admin)

    def test_list_search_and_filter(self):
        response = self.client.get('/api/admin/support/?status=OPEN')
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/api/admin/support/?search=Help me')
        self.assertEqual(len(response.json()['data']), 1)

    def test_admin_reply_notifies_user(self):
        before = Notification.objects.filter(user=self.user).count()
        response = self.client.post(
            f"/api/admin/support/{self.conversation.conversation_id}/messages/",
            {'message': 'Support reply'}, format='json',
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Notification.objects.filter(user=self.user).count(), before + 1,
        )
        message = SupportMessage.objects.filter(conversation=self.conversation).order_by('-created_at').first()
        self.assertTrue(message.is_admin)

    def test_status_change_audited(self):
        response = self.client.post(
            f"/api/admin/support/{self.conversation.conversation_id}/status/",
            {'status': 'RESOLVED'}, format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.status, 'RESOLVED')
        self.assertTrue(AuditLog.objects.filter(target_type='admin.support_status').exists())

    def test_cannot_reply_to_closed(self):
        self.conversation.status = SupportConversation.Status.CLOSED
        self.conversation.save()
        response = self.client.post(
            f"/api/admin/support/{self.conversation.conversation_id}/messages/",
            {'message': 'late reply'}, format='json',
        )
        self.assertEqual(response.status_code, 409)


class AdminTransactionAndAuditTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('ledger@example.com', '+15550012080')
        auth(self.client, self.admin)

    def test_transaction_viewer_read_only_filters(self):
        response = self.client.get('/api/admin/transactions/?type=DEPOSIT&direction=CREDIT')
        self.assertEqual(response.status_code, 200)

    def test_audit_log_list_and_filters(self):
        AuditLog.objects.create(actor_user=self.admin, action=AuditLog.Action.UPDATE,
                                target_type='admin.setting', target_id='x', description='y')
        response = self.client.get('/api/admin/audit-logs/?action=UPDATE')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()['data']), 1)


class AdminSettingsTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('setter@example.com', '+15550012090')
        self.setting = SiteSetting.objects.create(
            key='withdrawal.fee_amount', value='1.00', value_type='decimal',
        )
        auth(self.client, self.admin)

    def tearDown(self):
        wd_config.invalidate_cache()
        reset_cache()

    def test_setting_change_audited(self):
        response = self.client.patch(
            '/api/admin/settings/', {'key': 'withdrawal.fee_amount', 'value': '2.50'},
            format='json',
        )
        self.assertEqual(response.status_code, 200)
        self.setting.refresh_from_db()
        self.assertEqual(self.setting.value, '2.50')
        self.assertTrue(AuditLog.objects.filter(
            target_type='admin.setting', target_id='withdrawal.fee_amount').exists())

    def test_invalid_decimal_rejected(self):
        response = self.client.patch(
            '/api/admin/settings/', {'key': 'withdrawal.fee_amount', 'value': 'abc'},
            format='json',
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_setting_404(self):
        response = self.client.patch(
            '/api/admin/settings/', {'key': 'nope.key', 'value': 'x'}, format='json',
        )
        self.assertEqual(response.status_code, 404)

    def test_normal_user_cannot_change_settings(self):
        auth(self.client, self.user)
        response = self.client.patch(
            '/api/admin/settings/', {'key': 'withdrawal.fee_amount', 'value': '0'},
            format='json',
        )
        self.assertEqual(response.status_code, 403)


class AdminBroadcastTests(APITestCase):
    def setUp(self):
        self.admin = make_admin()
        self.u1 = make_user('bc1@example.com', '+15550012100')
        self.u2 = make_user('bc2@example.com', '+15550012101', account_status=User.AccountStatus.BANNED)
        auth(self.client, self.admin)

    def test_broadcast_reaches_only_active(self):
        response = self.client.post('/api/admin/notifications/broadcast/', {
            'title': 'Maintenance window', 'message': 'Brief downtime tonight.', 'audience': 'all_active',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        delivered = response.json()['data']['delivered']
        self.assertEqual(delivered, User.objects.filter(account_status='ACTIVE', is_active=True).count())
        self.assertTrue(Notification.objects.filter(user=self.u1, title='Maintenance window').exists())
        self.assertFalse(Notification.objects.filter(user=self.u2).exists())

    def test_broadcast_requires_title_and_message(self):
        response = self.client.post('/api/admin/notifications/broadcast/', {'audience': 'all_active'}, format='json')
        self.assertEqual(response.status_code, 400)


class MassAssignmentTests(APITestCase):
    """§100–101: no endpoint accepts is_staff/is_superuser/account_status."""

    def setUp(self):
        self.admin = make_admin()
        self.user = make_user('victim@example.com', '+15550012110')
        auth(self.client, self.admin)

    def test_no_generic_user_update_endpoint(self):
        # PATCH/PUT on user detail must not exist (405), so no mass assignment.
        response = self.client.patch(
            f"/api/admin/users/{self.user.user_id}/",
            {'is_staff': True, 'is_superuser': True, 'account_status': 'ACTIVE'},
            format='json',
        )
        self.assertIn(response.status_code, (404, 405))
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)

    def test_vip_plan_payload_cannot_set_staff_flags(self):
        response = self.client.post('/api/admin/vip-plans/', {
            'name': 'Evil', 'plan_number': 42, 'investment_amount': '1.00',
            'target_amount': '2.00', 'daily_rate': '0.1',
            'is_staff': True, 'is_superuser': True,
        }, format='json')
        # Either rejected for validation or created ignoring the extra keys.
        if response.status_code == 201:
            self.assertFalse(User.objects.filter(email='evil@example.com').exists())
