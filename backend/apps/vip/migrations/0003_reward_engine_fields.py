"""Migration: reward-engine fields on VIPReward + cycle marker on VIPPurchase.

- VIPReward.processed_at / error_info: processing bookkeeping (§7, §30).
- VIPReward indexes for the history/eligibility queries (§48).
- VIPReward check constraints: credited ≥ 0 and credited ≤ calculated (§48).
- VIPPurchase.last_reward_cycle: records a cycle fully consumed by the
  target cap so a zero-remaining cycle can never pay twice (§6, §8).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vip', '0002_vippurchase_idempotency_key_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='vippurchase',
            name='last_reward_cycle',
            field=models.DateField(blank=True, db_index=True, help_text='Last reward cycle fully consumed (target cap reached mid-cycle).', null=True),
        ),
        migrations.AddField(
            model_name='vipreward',
            name='processed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='vipreward',
            name='error_info',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
        migrations.AddIndex(
            model_name='vipreward',
            index=models.Index(fields=['user', '-reward_date'], name='vipreward_user_date_idx'),
        ),
        migrations.AddIndex(
            model_name='vipreward',
            index=models.Index(fields=['vip_purchase', 'status'], name='vipreward_purchase_status_idx'),
        ),
        migrations.AddIndex(
            model_name='vipreward',
            index=models.Index(fields=['reward_date', 'status'], name='vipreward_date_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='vipreward',
            constraint=models.CheckConstraint(check=models.Q(credited_amount__gte=0), name='vipreward_credited_nonnegative'),
        ),
        migrations.AddConstraint(
            model_name='vipreward',
            constraint=models.CheckConstraint(check=models.Q(credited_amount__lte=models.F('calculated_amount')), name='vipreward_credited_lte_calculated'),
        ),
    ]
