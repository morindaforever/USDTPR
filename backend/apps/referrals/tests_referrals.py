"""Referral system tests (Section 9).

Covers: relationship creation/eligibility/cycles/one-referrer (§57–58, §64),
tree levels (§63), commission calculation across plans and levels (§59),
target reward coupling (§12), idempotent duplicates (§60), wallet-failure
rollback (§65), historical rate snapshots (§62), no-commission-on-deposit/
registration/commission (§36–37, §77), concurrency (§61), and API
authorization/isolation (§57).
"""

from datetime import timedelta
from decimal import Decimal
from threading import Barrier, Thread
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import register_user
from apps.core.models import AuditLog
from apps.deposits.models import Deposit
from apps.notifications.models import Notification
from apps.referrals import config
from apps.referrals.commission_service import (
    calculate_commission,
    on_referral_reward_credited,
    process_referral_commission,
)
from apps.referrals.models import Referral, ReferralCommission
from apps.referrals.services import ReferralError, create_relationship
from apps.referrals.tree import ancestors_with_levels
from apps.vip.models import VIPPlan, VIPPurchase, VIPReward
from apps.vip.reward_service import current_cycle, process_reward
from apps.wallet.models import WalletTransaction
from apps.wallet.services import admin_adjust, get_wallet_summary

PASSWORD = 'S3curePass!x'


def _mk(email: str, i: int, referrer: User | None = None) -> User:
    return register_user(
        full_name=email.split('@')[0].upper(),
        email=email,
        phone=f'+1991234{i:05d}',
        password=PASSWORD,
        referral_code=referrer.referral_code if referrer else '',
    ).user


def _fund(user, amount: str) -> None:
    admin_adjust(
        user=user,
        amount=Decimal(amount),
        balance_type=WalletTransaction.BalanceType.WITHDRAWABLE,
        direction=WalletTransaction.Direction.CREDIT,
        reason='test funding',
    )


def _buy_vip1(user, key: str) -> VIPPurchase:
    _fund(user, '50')
    plan = VIPPlan.objects.filter(name='VIP 1').first()
    assert plan is not None, 'seeded plans missing'
    from apps.vip.services import purchase_plan

    return purchase_plan(user=user, plan_id=plan.id, idempotency_key=key).purchase


class ReferralChainTestCase(TestCase):
    """Shared A→B→C→D fixture for tree and commission tests."""

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', verbosity=0)
        cls.a = _mk('chain-a@example.com', 1001)
        cls.b = _mk('chain-b@example.com', 1002, referrer=cls.a)
        cls.c = _mk('chain-c@example.com', 1003, referrer=cls.b)
        cls.d = _mk('chain-d@example.com', 1004, referrer=cls.c)


class RegistrationReferralTests(TestCase):
    """Signup-side validation (§5–6, §57)."""

    def test_valid_code_creates_relationship(self) -> None:
        referrer = _mk('reg-ref@example.com', 2001)
        new = _mk('reg-new@example.com', 2002, referrer=referrer)
        self.assertEqual(new.referred_by, referrer)
        self.assertTrue(Referral.objects.filter(referrer=referrer, referred_user=new).exists())

    def test_invalid_code_rejected(self) -> None:
        with self.assertRaises(Exception):
            _mk('reg-bad@example.com', 2003) if False else register_user(
                full_name='X', email='reg-bad@example.com', phone='+19912342003',
                password=PASSWORD, referral_code='NOPE123',
            )

    def test_no_code_ok(self) -> None:
        user = _mk('reg-solo@example.com', 2004)
        self.assertIsNone(user.referred_by)

    def test_suspended_referrer_rejected(self) -> None:
        referrer = _mk('reg-susp@example.com', 2005)
        referrer.account_status = User.AccountStatus.SUSPENDED
        referrer.save(update_fields=['account_status'])
        with self.assertRaises(Exception):
            _mk('reg-via-susp@example.com', 2006, referrer=referrer)

    def test_banned_referrer_rejected(self) -> None:
        referrer = _mk('reg-ban@example.com', 2007)
        referrer.account_status = User.AccountStatus.BANNED
        referrer.save(update_fields=['account_status'])
        with self.assertRaises(Exception):
            _mk('reg-via-ban@example.com', 2008, referrer=referrer)

    def test_duplicate_relationship_rejected_by_service(self) -> None:
        referrer = _mk('reg-dup@example.com', 2009)
        new = _mk('reg-dup2@example.com', 2010, referrer=referrer)
        other = _mk('reg-dup3@example.com', 2011)
        with self.assertRaises(ReferralError):
            create_relationship(referrer=other, referred_user=new)

    def test_same_relationship_idempotent(self) -> None:
        referrer = _mk('reg-idem@example.com', 2012)
        new = _mk('reg-idem2@example.com', 2013, referrer=referrer)
        result = create_relationship(referrer=referrer, referred_user=new)
        self.assertFalse(result.created)

    def test_no_commission_on_registration(self) -> None:
        referrer = _mk('reg-nocomm@example.com', 2014)
        _mk('reg-nocomm2@example.com', 2015, referrer=referrer)
        self.assertEqual(ReferralCommission.objects.count(), 0)

    def test_signup_notification_to_referrer(self) -> None:
        referrer = _mk('reg-notif@example.com', 2016)
        _mk('reg-notif2@example.com', 2017, referrer=referrer)
        self.assertTrue(
            Notification.objects.filter(
                user=referrer, notification_type=Notification.NotificationType.REFERRAL,
            ).exists()
        )

    def test_audit_log_created(self) -> None:
        referrer = _mk('reg-audit@example.com', 2018)
        _mk('reg-audit2@example.com', 2019, referrer=referrer)
        self.assertTrue(
            AuditLog.objects.filter(target_type='referral').exists()
        )


class CycleAndTreeTests(ReferralChainTestCase):
    """Cycle protection and level walking (§22, §63–64)."""

    def test_direct_referral_is_level_1(self) -> None:
        pairs = ancestors_with_levels(self.b)
        self.assertEqual([(u.user_id, lvl) for u, lvl, _ in pairs], [(self.a.user_id, 1)])

    def test_levels_1_2_3(self) -> None:
        pairs = ancestors_with_levels(self.d)
        self.assertEqual(
            [(u.user_id, lvl) for u, lvl, _ in pairs],
            [(self.c.user_id, 1), (self.b.user_id, 2), (self.a.user_id, 3)],
        )

    def test_max_level_configurable_and_bounded(self) -> None:
        self.assertEqual(config.get_max_level(), 3)
        with patch.object(config, 'get_max_level', return_value=2):
            pairs = ancestors_with_levels(self.d)
            self.assertEqual([lvl for _, lvl, _ in pairs], [1, 2])

    def test_cycle_rejected(self) -> None:
        # A → B → C → D exists; making A's referrer D would close a cycle.
        with self.assertRaises(ReferralError):
            create_relationship(referrer=self.d, referred_user=self.a)

    def test_blocked_relationship_severs_branch(self) -> None:
        Referral.objects.filter(referrer=self.c).update(status=Referral.Status.BLOCKED)
        pairs = ancestors_with_levels(self.d)
        self.assertEqual(pairs, [])

    def test_inactive_referrer_skipped_but_chain_continues(self) -> None:
        self.c.is_active = False
        self.c.save(update_fields=['is_active'])
        pairs = ancestors_with_levels(self.d)
        levels = {lvl: u.user_id for u, lvl, _ in pairs}
        self.assertNotIn(1, levels)
        self.assertEqual(levels.get(2), self.b.user_id)
        self.assertEqual(levels.get(3), self.a.user_id)


class CommissionCalculationTests(ReferralChainTestCase):
    """Decimal math, per-level rates, target coupling (§13–14, §59)."""

    def _reward_for(self, user, credited: Decimal) -> VIPReward:
        purchase = _buy_vip1(user, f'calc-{user.user_id}-{credited}')
        cycle = current_cycle()
        return VIPReward.objects.create(
            user=user,
            vip_purchase=purchase,
            reward_date=cycle,
            calculated_amount=credited,
            credited_amount=credited,
            status=VIPReward.Status.COMPLETED,
        )

    def test_calculate_decimal_values(self) -> None:
        cases = [
            ('10.00', '1.00000000'),    # L1 10%
            ('25.00', '2.50000000'),
            ('12.50', '1.25000000'),
            ('37.50', '3.75000000'),
            ('125.00', '12.50000000'),
        ]
        for amount, expected in cases:
            self.assertEqual(calculate_commission(Decimal(amount), Decimal('10')), Decimal(expected))

    def test_level_rates(self) -> None:
        reward = self._reward_for(self.d, Decimal('10.00'))
        outcomes = on_referral_reward_credited(reward)
        by_level = {o.level: o for o in outcomes}
        self.assertEqual(by_level[1].amount, Decimal('1.00000000'))
        self.assertEqual(by_level[2].amount, Decimal('0.50000000'))
        self.assertEqual(by_level[3].amount, Decimal('0.20000000'))

    def test_balances_and_ledger_agree(self) -> None:
        reward = self._reward_for(self.d, Decimal('25.00'))
        on_referral_reward_credited(reward)
        # Issue 6: each member also holds a 1 USDT signup reward paid by
        # their downline signup (b→a, c→b, d→c), so expected = commission + 1.
        for user, expected in [(self.c, '3.50'), (self.b, '2.25'), (self.a, '1.50')]:
            summary = get_wallet_summary(user)
            self.assertEqual(summary['withdrawable_balance'], Decimal(expected).quantize(Decimal('0.00000001')))
            txn = WalletTransaction.objects.filter(
                user=user, transaction_type=WalletTransaction.TransactionType.REFERRAL_COMMISSION,
            )
            self.assertEqual(txn.count(), 1)
            self.assertEqual(txn.first().amount, Decimal(expected) - Decimal('1'))
            self.assertEqual(txn.first().direction, WalletTransaction.Direction.CREDIT)

    def test_rate_and_level_snapshotted(self) -> None:
        reward = self._reward_for(self.d, Decimal('10.00'))
        on_referral_reward_credited(reward)
        comm = ReferralCommission.objects.get(user=self.c)
        self.assertEqual(comm.commission_rate, Decimal('0.1000'))
        self.assertEqual(comm.level, 1)
        self.assertEqual(comm.source_reward_amount, Decimal('10.00000000'))
        self.assertEqual(comm.cycle_date, reward.reward_date)

    def test_historical_rate_survives_config_change(self) -> None:
        reward = self._reward_for(self.d, Decimal('10.00'))
        on_referral_reward_credited(reward)
        before = ReferralCommission.objects.get(user=self.c).commission_amount

        setting, _ = config.KEY_LEVEL_RATE.format(level=1), None
        from apps.core.models import SiteSetting
        SiteSetting.objects.update_or_create(
            key=config.KEY_LEVEL_RATE.format(level=1),
            defaults={'value': '5', 'value_type': SiteSetting.ValueType.DECIMAL},
        )
        config.reset_cache()
        try:
            self.assertEqual(ReferralCommission.objects.get(user=self.c).commission_amount, before)
            self.assertEqual(ReferralCommission.objects.get(user=self.c).commission_rate, Decimal('0.1000'))
            # New reward for another user uses the new rate.
            e = _mk('chain-e@example.com', 1005, referrer=self.d)
            reward2 = self._reward_for(e, Decimal('10.00'))
            on_referral_reward_credited(reward2)
            new_comm = ReferralCommission.objects.get(user=self.d, source_reward=reward2)
            self.assertEqual(new_comm.commission_rate, Decimal('0.0500'))
            self.assertEqual(new_comm.commission_amount, Decimal('0.50000000'))
        finally:
            SiteSetting.objects.filter(key=config.KEY_LEVEL_RATE.format(level=1)).delete()
            config.reset_cache()

    def test_duplicate_reward_processed_once(self) -> None:
        reward = self._reward_for(self.d, Decimal('10.00'))
        on_referral_reward_credited(reward)
        outcomes = on_referral_reward_credited(reward)
        self.assertTrue(all(o.status == 'already_credited' for o in outcomes))
        self.assertEqual(ReferralCommission.objects.filter(source_user=reward.user).count(), 3)

    def test_failed_reward_generates_no_commission(self) -> None:
        purchase = _buy_vip1(self.d, 'failed-reward')
        reward = VIPReward.objects.create(
            user=self.d, vip_purchase=purchase, reward_date=current_cycle(),
            calculated_amount=Decimal('2.5'), credited_amount=Decimal('2.5'),
            status=VIPReward.Status.FAILED,
        )
        with self.assertRaises(Exception):
            process_referral_commission(reward.reward_id)
        self.assertEqual(ReferralCommission.objects.filter(source_user=self.d).count(), 0)

    def test_no_commission_on_deposit(self) -> None:
        network = Deposit._meta.get_field('network').related_model.objects.create(name='T', code='T9')
        Deposit.objects.create(
            user=self.d, network=network, amount=Decimal('500'), deposit_address='0xdead',
        )
        self.assertEqual(ReferralCommission.objects.count(), 0)

    def test_no_commission_on_other_commission(self) -> None:
        reward = self._reward_for(self.d, Decimal('10.00'))
        on_referral_reward_credited(reward)
        count = ReferralCommission.objects.count()
        # Re-processing the commission set cannot grow it (§36).
        reward2 = VIPReward.objects.get(pk=reward.pk)
        on_referral_reward_credited(reward2)
        self.assertEqual(ReferralCommission.objects.count(), count)

    def test_wallet_failure_marks_failed_not_fatal(self) -> None:
        reward = self._reward_for(self.d, Decimal('10.00'))
        # Baselines include the 1 USDT signup rewards already credited on
        # signup (Issue 6) — commissions failing must not move them.
        baseline = {u: get_wallet_summary(u)['withdrawable_balance'] for u in (self.a, self.b, self.c)}
        with patch('apps.referrals.commission_service.credit') as mock_credit:
            from apps.wallet.services import WalletError

            mock_credit.side_effect = WalletError('wallet down')
            outcomes = on_referral_reward_credited(reward)
        self.assertTrue(all(o.status == 'failed' for o in outcomes))
        self.assertTrue(all(c.status == ReferralCommission.Status.FAILED for c in ReferralCommission.objects.filter(source_user=self.d)))
        # Balances untouched by the FAILED commissions.
        for user in (self.a, self.b, self.c):
            self.assertEqual(get_wallet_summary(user)['withdrawable_balance'], baseline[user])
        # Retry with working wallet repays the FAILED rows, not duplicates.
        outcomes2 = on_referral_reward_credited(reward)
        self.assertTrue(all(o.status == 'credited' for o in outcomes2))
        self.assertEqual(ReferralCommission.objects.filter(source_user=self.d).count(), 3)


class ReferralAPITests(ReferralChainTestCase):
    """API authorization and isolation (§57, §67)."""

    def setUp(self) -> None:
        from rest_framework.test import APIClient

        self.client = APIClient()

    def _auth(self, user) -> None:
        from rest_framework_simplejwt.tokens import RefreshToken

        token = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.access_token}')

    def test_summary_requires_auth(self) -> None:
        response = self.client.get('/api/referrals/summary/')
        self.assertEqual(response.status_code, 401)

    def test_summary_shape(self) -> None:
        self._auth(self.a)
        response = self.client.get('/api/referrals/summary/')
        self.assertEqual(response.status_code, 200)
        data = response.json()['data']
        self.assertEqual(data['referral_code'], self.a.referral_code)
        self.assertIn('ref=', data['referral_link'])
        self.assertEqual(data['direct_referrals'], 1)
        self.assertEqual(data['total_team'], 3)
        self.assertEqual(data['level_counts']['1'], 1)
        self.assertEqual(data['commission_rates']['1'], '10.00')

    def test_referral_link_never_leaks_localhost_in_production(self) -> None:
        """Unconfigured PUBLIC_APP_URL in production → relative path, not localhost."""
        from django.test import override_settings

        from .serializers import build_referral_link

        self._auth(self.a)
        with override_settings(PUBLIC_APP_URL='', DEBUG=False):
            self.assertEqual(build_referral_link('ABC123'), '/signup?ref=ABC123')
            response = self.client.get('/api/referrals/summary/')
            self.assertEqual(response.status_code, 200)
            link = response.json()['data']['referral_link']
            self.assertTrue(link.startswith('/signup?ref='), link)
            self.assertNotIn('localhost', link)
            self.assertNotIn('http', link)

    def test_referral_link_uses_configured_base_and_encodes_code(self) -> None:
        from django.test import override_settings

        from .serializers import build_referral_link

        with override_settings(PUBLIC_APP_URL='https://nexus.example.com/'):
            self.assertEqual(build_referral_link('ABC123'), 'https://nexus.example.com/signup?ref=ABC123')
        with override_settings(PUBLIC_APP_URL='', DEBUG=True):
            self.assertEqual(build_referral_link('ABC123'), 'http://localhost:5173/signup?ref=ABC123')

    def test_team_isolation(self) -> None:
        stranger = _mk('api-stranger@example.com', 3001)
        self._auth(stranger)
        response = self.client.get('/api/referrals/team/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['data'], [])

    def test_team_levels_and_filters(self) -> None:
        self._auth(self.a)
        response = self.client.get('/api/referrals/team/')
        levels = {m['level'] for m in response.json()['data']}
        self.assertEqual(levels, {1, 2, 3})

        response = self.client.get('/api/referrals/team/?level=2')
        self.assertEqual({m['level'] for m in response.json()['data']}, {2})

    def test_commission_detail_isolation(self) -> None:
        reward = _buy_vip1(self.d, 'api-reward')
        # Give D a reward so C has a commission to view.
        vip_reward = VIPReward.objects.create(
            user=self.d, vip_purchase=reward, reward_date=current_cycle(),
            calculated_amount=Decimal('2.5'), credited_amount=Decimal('2.5'),
            status=VIPReward.Status.COMPLETED,
        )
        process_referral_commission(vip_reward.reward_id)
        comm = ReferralCommission.objects.get(user=self.c)

        self._auth(self.c)
        ok = self.client.get(f"/api/referrals/commissions/{comm.commission_id}/")
        self.assertEqual(ok.status_code, 200)

        self._auth(self.b)
        stolen = self.client.get(f"/api/referrals/commissions/{comm.commission_id}/")
        self.assertEqual(stolen.status_code, 404)

    def test_commission_list_filters(self) -> None:
        reward_purchase = _buy_vip1(self.d, 'api-filter')
        vip_reward = VIPReward.objects.create(
            user=self.d, vip_purchase=reward_purchase, reward_date=current_cycle(),
            calculated_amount=Decimal('2.5'), credited_amount=Decimal('2.5'),
            status=VIPReward.Status.COMPLETED,
        )
        process_referral_commission(vip_reward.reward_id)

        self._auth(self.a)
        response = self.client.get('/api/referrals/commissions/?level=3')
        items = response.json()['data']
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['commission_rate_percent'], '2.00')


class CommissionConcurrencyTests(TransactionTestCase):
    """Racing workers must pay exactly once (§61)."""

    def setUp(self) -> None:
        # TransactionTestCase flushes tables between tests — reseed.
        call_command('seed_demo_data', verbosity=0)

    def test_parallel_processing_single_commission(self) -> None:
        a = _mk('conc-a@example.com', 4001)
        b = _mk('conc-b@example.com', 4002, referrer=a)
        _fund(b, '50')
        purchase = _buy_vip1(b, 'conc-purchase')
        reward = VIPReward.objects.create(
            user=b, vip_purchase=purchase, reward_date=current_cycle(),
            calculated_amount=Decimal('2.5'), credited_amount=Decimal('2.5'),
            status=VIPReward.Status.COMPLETED,
        )

        barrier = Barrier(2)
        results: list = []

        def worker() -> None:
            from django.db import connection

            connection.close()
            barrier.wait()
            results.append(on_referral_reward_credited(reward))
            connection.close()

        threads = [Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)

        commissions = ReferralCommission.objects.filter(source_user=b)
        self.assertEqual(commissions.count(), 1)  # A is B's only ancestor
        self.assertEqual(
            commissions.filter(status=ReferralCommission.Status.CREDITED).count(), 1,
        )
        ledger = WalletTransaction.objects.filter(
            user=a, transaction_type=WalletTransaction.TransactionType.REFERRAL_COMMISSION,
        )
        self.assertEqual(ledger.count(), 1)


class ReferralSignupRewardTests(TestCase):
    """Issue 6 — one-time 1 USDT signup reward to the referrer.

    Paid through the existing wallet ledger (REFERRAL_REWARD → withdrawable),
    exactly once per referred member, idempotent on retries, and never a
    deposit/commission transaction.
    """

    @classmethod
    def setUpTestData(cls) -> None:
        call_command('seed_demo_data', verbosity=0)
        config.reset_cache()

    def _reward_rows(self, user):
        return WalletTransaction.objects.filter(
            user=user,
            transaction_type=WalletTransaction.TransactionType.REFERRAL_REWARD,
            status=WalletTransaction.Status.COMPLETED,
        )

    def test_referrer_receives_exactly_1_usdt(self) -> None:
        referrer = _mk('reward-ref@example.com', 5001)
        _mk('reward-new@example.com', 5002, referrer=referrer)
        rows = self._reward_rows(referrer)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().amount, Decimal('1'))
        self.assertEqual(rows.get().balance_type, WalletTransaction.BalanceType.WITHDRAWABLE)
        summary = get_wallet_summary(referrer)
        self.assertEqual(summary['withdrawable_balance'], Decimal('1'))

    def test_reward_is_never_a_deposit_or_commission(self) -> None:
        referrer = _mk('reward-kind@example.com', 5003)
        _mk('reward-kind2@example.com', 5004, referrer=referrer)
        self.assertFalse(
            WalletTransaction.objects.filter(
                user=referrer, transaction_type=WalletTransaction.TransactionType.DEPOSIT,
            ).exists()
        )
        self.assertEqual(ReferralCommission.objects.count(), 0)

    def test_reward_references_the_referral(self) -> None:
        referrer = _mk('reward-refref@example.com', 5005)
        new_user = _mk('reward-new2@example.com', 5006, referrer=referrer)
        row = self._reward_rows(referrer).get()
        self.assertEqual(row.reference_type, 'referral')
        self.assertEqual(row.reference_id, str(new_user.pk))
        self.assertIn('signup reward', row.description.lower())
        self.assertEqual(row.idempotency_key, f'REFERRAL_REWARD_{new_user.pk}')

    def test_repeated_relationship_calls_cannot_duplicate(self) -> None:
        referrer = _mk('reward-idem@example.com', 5007)
        new_user = _mk('reward-idem2@example.com', 5008, referrer=referrer)
        create_relationship(referrer=referrer, referred_user=new_user)
        create_relationship(referrer=referrer, referred_user=new_user)
        self.assertEqual(self._reward_rows(referrer).count(), 1)

    def test_self_referral_pays_nothing(self) -> None:
        user = _mk('reward-self@example.com', 5009)
        with self.assertRaises(ReferralError):
            create_relationship(referrer=user, referred_user=user)
        self.assertEqual(self._reward_rows(user).count(), 0)

    def test_invalid_referral_code_never_rewards(self) -> None:
        with self.assertRaises(Exception):
            register_user(
                full_name='X', email='reward-badcode@example.com', phone='+19912345010',
                password=PASSWORD, referral_code='ZZZZ999',
            )
        self.assertFalse(
            WalletTransaction.objects.filter(
                transaction_type=WalletTransaction.TransactionType.REFERRAL_REWARD,
            ).exists()
        )

    def test_two_referrals_reward_twice(self) -> None:
        referrer = _mk('reward-two@example.com', 5011)
        _mk('reward-two2@example.com', 5012, referrer=referrer)
        _mk('reward-two3@example.com', 5013, referrer=referrer)
        self.assertEqual(self._reward_rows(referrer).count(), 2)
        self.assertEqual(get_wallet_summary(referrer)['withdrawable_balance'], Decimal('2'))

    def test_reward_amount_is_configurable(self) -> None:
        from apps.core.models import SiteSetting

        referrer = _mk('reward-cfg@example.com', 5016)
        SiteSetting.objects.create(key=config.KEY_SIGNUP_REWARD, value='2.5')
        config.reset_cache()
        try:
            _mk('reward-cfg2@example.com', 5017, referrer=referrer)
            rows = self._reward_rows(referrer)
            self.assertEqual(rows.count(), 1)
            self.assertEqual(rows.get().amount, Decimal('2.5'))
        finally:
            SiteSetting.objects.filter(key=config.KEY_SIGNUP_REWARD).delete()
            config.reset_cache()

    def test_member_list_still_works_with_reward(self) -> None:
        referrer = _mk('reward-list@example.com', 5018)
        _mk('reward-list2@example.com', 5019, referrer=referrer)
        self.assertTrue(Referral.objects.filter(referrer=referrer).exists())
        self.assertTrue(
            Notification.objects.filter(
                user=referrer, notification_type=Notification.NotificationType.REFERRAL,
            ).exists()
        )
