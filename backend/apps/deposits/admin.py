"""Admin registration for deposits."""

from django.contrib import admin

from .models import Deposit


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = (
        'deposit_id',
        'user',
        'network',
        'asset',
        'amount',
        'order_id',
        'tx_hash',
        'status',
        'created_at',
    )
    list_filter = ('status', 'network', 'asset', 'created_at')
    search_fields = ('deposit_id', 'order_id', 'tx_hash', 'user__email', 'user__user_id')
    readonly_fields = (
        'deposit_id',
        'created_at',
        'updated_at',
        'approved_at',
        'rejected_at',
    )
    date_hierarchy = 'created_at'
