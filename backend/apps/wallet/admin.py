"""Admin registration for wallet app."""

from django.contrib import admin

from .models import DepositAddress, Network, Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'total_balance',
        'deposit_balance',
        'withdrawable_balance',
        'pending_balance',
        'locked_balance',
        'bonus_balance',
        'updated_at',
    )
    search_fields = ('user__email', 'user__user_id')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_id',
        'user',
        'transaction_type',
        'direction',
        'balance_type',
        'amount',
        'status',
        'created_at',
    )
    list_filter = ('transaction_type', 'direction', 'balance_type', 'status', 'created_at')
    search_fields = ('transaction_id', 'user__email', 'user__user_id', 'reference_id', 'idempotency_key')
    readonly_fields = (
        'transaction_id',
        'created_at',
        'updated_at',
        'idempotency_key',
    )
    date_hierarchy = 'created_at'


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'asset', 'is_active', 'sort_order', 'updated_at')
    list_filter = ('is_active', 'asset')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(DepositAddress)
class DepositAddressAdmin(admin.ModelAdmin):
    list_display = ('network', 'asset', 'address', 'is_active', 'created_at')
    list_filter = ('network', 'asset', 'is_active')
    search_fields = ('address',)
    readonly_fields = ('created_at', 'updated_at')
