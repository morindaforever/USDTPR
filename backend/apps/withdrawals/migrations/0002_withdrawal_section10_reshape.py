"""Reshape Withdrawal for Section 10: fee/net snapshots + idempotency.

The Section-2 Withdrawal model had no fee snapshot, no idempotency key, and
no state-machine timestamps, and was never wired into production code
(0 rows in every environment). This migration replaces it with the Section 10
shape: requested/fee/net amounts, per-user unique idempotency key, rejection
reason, processing/failed timestamps, and the reviewing admin FK.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import apps.core.db


class Migration(migrations.Migration):

    dependencies = [
        ('withdrawals', '0001_initial'),
        ('wallet', '0003_alter_wallettransaction_transaction_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(
            name='Withdrawal',
        ),
        migrations.CreateModel(
            name='Withdrawal',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('withdrawal_id', apps.core.db.HumanIDField(
                    db_index=True, editable=False, max_length=19, padding=8, prefix='WDR', unique=True)),
                ('asset', models.CharField(default='USDT', max_length=10)),
                ('requested_amount', apps.core.db.money_field()),
                ('fee_amount', apps.core.db.money_field(default=0)),
                ('net_amount', apps.core.db.money_field(default=0)),
                ('wallet_address', models.CharField(max_length=255)),
                ('status', models.CharField(
                    choices=[
                        ('PENDING', 'Pending'),
                        ('APPROVED', 'Approved'),
                        ('REJECTED', 'Rejected'),
                        ('PROCESSING', 'Processing'),
                        ('COMPLETED', 'Completed'),
                        ('FAILED', 'Failed'),
                    ],
                    db_index=True, default='PENDING', max_length=12)),
                ('tx_hash', models.CharField(blank=True, max_length=128)),
                ('rejection_reason', models.CharField(blank=True, default='', max_length=255)),
                ('admin_note', models.TextField(blank=True)),
                ('idempotency_key', models.CharField(blank=True, default='', max_length=128)),
                ('requested_at', models.DateTimeField(auto_now_add=True)),
                ('approved_at', models.DateTimeField(blank=True, null=True)),
                ('rejected_at', models.DateTimeField(blank=True, null=True)),
                ('processing_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('failed_at', models.DateTimeField(blank=True, null=True)),
                ('network', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='withdrawals',
                    to='wallet.network')),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='withdrawals',
                    to=settings.AUTH_USER_MODEL)),
                ('admin', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='withdrawals_reviewed',
                    to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='withdrawal',
            index=models.Index(fields=['user', '-created_at'], name='withdrawal_user_created_idx'),
        ),
        migrations.AddIndex(
            model_name='withdrawal',
            index=models.Index(fields=['status', '-created_at'], name='withdrawal_status_created_idx'),
        ),
        migrations.AddIndex(
            model_name='withdrawal',
            index=models.Index(fields=['network'], name='withdrawal_network_idx'),
        ),
        migrations.AddConstraint(
            model_name='withdrawal',
            constraint=models.CheckConstraint(check=models.Q(requested_amount__gt=0), name='withdrawal_amount_positive'),
        ),
        migrations.AddConstraint(
            model_name='withdrawal',
            constraint=models.CheckConstraint(check=models.Q(fee_amount__gte=0), name='withdrawal_fee_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='withdrawal',
            constraint=models.CheckConstraint(check=models.Q(net_amount__gte=0), name='withdrawal_net_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='withdrawal',
            constraint=models.UniqueConstraint(fields=('user', 'idempotency_key'), name='withdrawal_user_idem_unique'),
        ),
    ]
