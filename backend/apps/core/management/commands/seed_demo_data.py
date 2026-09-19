"""Seed development/demo configuration data.

Creates/updates only configuration rows — networks, VIP plans, withdrawal
rules. Never creates fake users, wallets, deposits, withdrawals, activity,
or valuations. Idempotent: safe to run repeatedly.

Production safety (§18): blocked unless DEBUG or a test run is active.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.vip.models import VIPPlan
from apps.wallet.models import Network
from apps.withdrawals.models import WithdrawalRule


def _ensure_not_production() -> None:
    """Refuse to run outside development/testing (§18)."""
    if not settings.DEBUG and not settings.TESTING:
        raise CommandError(
            'seed_demo_data is a development utility and is disabled when '
            'DEBUG=False. Configure production data (networks, plans, '
            'addresses) through the admin panel instead.'
        )


class Command(BaseCommand):
    help = (
        'Seed configuration reference rows (networks, VIP plans, withdrawal '
        'rules). Production conversion (§1/§18): creates NO financial '
        'activity and NO placeholder deposit addresses. Real deposit '
        'addresses are entered by operators via the admin; this command is '
        'blocked outside development/testing.'
    )

    def handle(self, *args, **options) -> None:
        _ensure_not_production()
        self._seed_networks()
        self._seed_vip_plans()
        self._seed_withdrawal_rules()
        self.stdout.write(self.style.SUCCESS('Seed complete.'))

    # ------------------------------------------------------------------ #
    def _seed_networks(self) -> None:
        networks = [
            ('BNB Smart Chain', 'BSC'),
            ('Tron', 'TRX'),
            ('Ethereum', 'ETH'),
            ('Polygon', 'POL'),
            ('Solana', 'SOL'),
            ('Toncoin', 'TON'),
        ]
        for sort_order, (name, code) in enumerate(networks, start=1):
            network, created = Network.objects.update_or_create(
                code=code,
                defaults={'name': name, 'asset': 'USDT', 'sort_order': sort_order, 'is_active': True},
            )
            self.stdout.write(f'  network {code}: {"created" if created else "updated"}')

    def _seed_vip_plans(self) -> None:
        # DEVELOPMENT configuration only. These numbers are not offers
        # or guarantees; product terms need a compliance review before any
        # real-money deployment.
        plans = [
            # (plan_number, name, investment, target, daily_rate)
            (0, 'WELCOME', '0', '10', '0.25'),
            (1, 'VIP 1', '10', '15', '0.25'),
            (2, 'VIP 2', '20', '30', '0.25'),
            (3, 'VIP 3', '50', '75', '0.25'),
            (4, 'VIP 4', '100', '150', '0.25'),
            (5, 'VIP 5', '150', '225', '0.25'),
            (6, 'VIP 6', '300', '500', '0.25'),
            (7, 'VIP 7', '500', '1000', '0.25'),
        ]
        for sort_order, (number, name, invest, target, rate) in enumerate(plans, start=1):
            plan, created = VIPPlan.objects.update_or_create(
                plan_number=number,
                defaults={
                    'name': name,
                    'investment_amount': Decimal(invest),
                    'target_amount': Decimal(target),
                    'daily_rate': Decimal(rate),
                    'sort_order': sort_order,
                    'is_active': True,
                },
            )
            self.stdout.write(f'  plan {name}: {"created" if created else "updated"}')

    def _seed_withdrawal_rules(self) -> None:
        # Thresholds use exclusive upper bounds: "amount > X" rows.
        # maximum_amount is the largest amount the rule covers.
        rules = [
            ('100', 'VIP 1'),   # amount <= 100
            ('500', 'VIP 3'),   # 100 < amount <= 500
            ('800', 'VIP 6'),   # 500 < amount <= 800
            ('999999999', 'VIP 7'),  # amount > 800
        ]
        for maximum, plan_name in rules:
            plan = VIPPlan.objects.filter(name=plan_name).first()
            if plan is None:
                self.stdout.write(self.style.WARNING(f'  plan {plan_name} missing; skipping rule'))
                continue
            rule, created = WithdrawalRule.objects.update_or_create(
                maximum_amount=Decimal(maximum),
                defaults={'required_vip_plan': plan, 'is_active': True},
            )
            self.stdout.write(f'  rule <= {maximum} → {plan_name}: {"created" if created else "updated"}')
