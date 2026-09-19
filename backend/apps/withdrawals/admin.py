"""Admin registration for withdrawals app."""

from django.contrib import admin

from .models import Withdrawal, WithdrawalRule


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    list_display = (
        'withdrawal_id',
        'user',
        'network',
        'asset',
        'requested_amount',
        'fee_amount',
        'net_amount',
        'wallet_address',
        'status',
        'created_at',
    )
    list_filter = ('status', 'network', 'asset', 'created_at')
    search_fields = ('withdrawal_id', 'wallet_address', 'tx_hash', 'user__email', 'user__user_id')
    readonly_fields = (
        'withdrawal_id',
        'idempotency_key',
        'created_at',
        'updated_at',
        'approved_at',
        'rejected_at',
        'processing_at',
        'completed_at',
        'failed_at',
    )
    date_hierarchy = 'created_at'


@admin.register(WithdrawalRule)
class WithdrawalRuleAdmin(admin.ModelAdmin):
    list_display = ('maximum_amount', 'required_vip_plan', 'is_active', 'updated_at')
    list_filter = ('is_active',)
    readonly_fields = ('created_at', 'updated_at')
