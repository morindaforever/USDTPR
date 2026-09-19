"""Reshape ReferralCommission: deposit-based → VIP-reward-based (Section 9).

The old deposit-based commission model was never wired into production code
(Section 2 skeleton only), and Section 9 §12/§37 define the commission source
as eligible **VIP rewards** — not deposits. This migration replaces the
deposit-linked model with the reward-linked one:

- beneficiary (``user``), ``source_user``, ``referral`` relationship row,
  ``level``, ``source_reward`` FK, snapshot amounts, ``cycle_date``,
  wallet txn reference, deterministic unique ``idempotency_key``.
- Referral gains the BLOCKED status choice and a referrer+status index.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.core.db


class Migration(migrations.Migration):

    dependencies = [
        ('referrals', '0001_initial'),
        ('vip', '0004_alter_vipreward_options_and_more'),
        ('wallet', '0003_alter_wallettransaction_transaction_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(
            name='ReferralCommission',
        ),
        migrations.AlterField(
            model_name='referral',
            name='status',
            field=models.CharField(
                choices=[
                    ('ACTIVE', 'Active'),
                    ('INACTIVE', 'Inactive'),
                    ('BLOCKED', 'Blocked'),
                ],
                default='ACTIVE',
                max_length=10,
            ),
        ),
        migrations.AddIndex(
            model_name='referral',
            index=models.Index(fields=['referrer', 'status'], name='referral_referrer_status_idx'),
        ),
        migrations.CreateModel(
            name='ReferralCommission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('commission_id', apps.core.db.HumanIDField(
                    db_index=True, editable=False, max_length=19, padding=8, prefix='COM', unique=True)),
                ('level', models.PositiveSmallIntegerField(db_index=True)),
                ('source_reward_amount', models.DecimalField(decimal_places=8, max_digits=24)),
                ('commission_rate', models.DecimalField(decimal_places=4, max_digits=5)),
                ('commission_amount', models.DecimalField(decimal_places=8, max_digits=24)),
                ('cycle_date', models.DateField(blank=True, db_index=True, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Pending'),
                        ('CREDITED', 'Credited'),
                        ('FAILED', 'Failed'),
                        ('REVERSED', 'Reversed'),
                    ],
                    db_index=True, default='PENDING', max_length=12)),
                ('idempotency_key', models.CharField(max_length=128, unique=True)),
                ('error_info', models.CharField(blank=True, default='', max_length=255)),
                ('processed_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='referral_commissions_earned',
                    to=settings.AUTH_USER_MODEL)),
                ('source_user', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='referral_commissions_generated',
                    to=settings.AUTH_USER_MODEL)),
                ('referral', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='commissions',
                    to='referrals.referral')),
                ('source_reward', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='referral_commissions',
                    to='vip.vipreward')),
                ('wallet_transaction', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='referral_commissions',
                    to='wallet.wallettransaction')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
