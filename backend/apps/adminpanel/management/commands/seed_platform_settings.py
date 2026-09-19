"""Seed SiteSetting rows so the admin panel can manage live configuration.

The withdrawal/referral config modules fall back to coded defaults when a
key is missing; seeding the rows makes the same values visible and editable
in /admin/settings without changing behaviour. Idempotent (get_or_create).
"""

from django.core.management.base import BaseCommand

from apps.core.models import SiteSetting


class Command(BaseCommand):
    help = 'Seed editable platform settings (idempotent; values keep coded defaults).'

    def handle(self, *args, **options) -> None:
        seeds = [
            # (key, value, value_type, description) — group is derived from the
            # key prefix (platform./deposit./withdrawal./referral./reward./support.)
            # General
            ('platform.support_email', 'support@nexususdt.local', 'string', 'general',
             'Support contact shown on Help pages.'),
            ('platform.maintenance_mode', 'false', 'boolean', 'maintenance',
             'When true, user-facing pages show a maintenance notice (admin panel stays accessible).'),
            # Deposit
            ('deposit.min_amount', '10.00', 'decimal', 'deposit',
             'Minimum deposit amount accepted (USDT).'),
            # Withdrawal — keys MUST match apps/withdrawals/config.py
            ('withdrawal.min_amount', '5.00', 'decimal', 'withdrawal',
             'Minimum withdrawal amount (USDT).'),
            ('withdrawal.fee_type', 'FIXED', 'string', 'withdrawal',
             'Fee model: FIXED or PERCENT.'),
            ('withdrawal.fee_amount', '1.00', 'decimal', 'withdrawal',
             'Fee value in USDT (FIXED) or percent (PERCENT).'),
            # Referral — keys MUST match apps/referrals/config.py
            ('referral.level_1_rate_percent', '10', 'decimal', 'referral',
             'Level 1 commission rate (%). Applies to new commissions only.'),
            ('referral.level_2_rate_percent', '5', 'decimal', 'referral',
             'Level 2 commission rate (%). Applies to new commissions only.'),
            ('referral.level_3_rate_percent', '2', 'decimal', 'referral',
             'Level 3 commission rate (%). Applies to new commissions only.'),
            ('referral.max_level', '3', 'integer', 'referral',
             'Maximum referral depth the engine walks.'),
            # Reward
            ('reward.processing_hour_utc', '0', 'integer', 'reward',
             'Hour (UTC) the daily reward cycle runs.'),
            # Security
            ('support.max_conversations_per_hour', '5', 'integer', 'security',
             'Rate limit: new support conversations per user per hour.'),
            ('support.max_messages_per_hour', '30', 'integer', 'security',
             'Rate limit: support messages per user per hour.'),
        ]
        created = 0
        for key, value, value_type, _group, description in seeds:
            _, was_created = SiteSetting.objects.get_or_create(
                key=key,
                defaults={
                    'value': value,
                    'value_type': value_type,
                    'description': description,
                },
            )
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Settings seeded: {created} created, {len(seeds) - created} already present.'))
