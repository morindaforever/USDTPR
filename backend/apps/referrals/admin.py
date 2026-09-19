"""Admin registration for referrals app."""

from django.contrib import admin

from .models import Referral, ReferralCommission


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ('id', 'referrer', 'referred_user', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('referrer__email', 'referred_user__email')


@admin.register(ReferralCommission)
class ReferralCommissionAdmin(admin.ModelAdmin):
    list_display = (
        'commission_id',
        'user',
        'source_user',
        'level',
        'source_reward_amount',
        'commission_rate',
        'commission_amount',
        'status',
        'cycle_date',
        'created_at',
    )
    list_filter = ('status', 'level', 'created_at')
    search_fields = ('commission_id', 'user__email', 'source_user__email')
    readonly_fields = (
        'commission_id',
        'idempotency_key',
        'created_at',
        'updated_at',
    )
