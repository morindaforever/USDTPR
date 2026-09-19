"""Admin registration for VIP app."""

from django.contrib import admin

from .models import VIPPlan, VIPPurchase, VIPReward


@admin.register(VIPPlan)
class VIPPlanAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'plan_number',
        'investment_amount',
        'target_amount',
        'daily_rate',
        'is_active',
        'sort_order',
    )
    list_filter = ('is_active',)
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(VIPPurchase)
class VIPPurchaseAdmin(admin.ModelAdmin):
    list_display = (
        'purchase_id',
        'user',
        'plan_name_snapshot',
        'investment_amount',
        'target_amount',
        'daily_rate_snapshot',
        'amount_received',
        'status',
        'created_at',
    )
    list_filter = ('status', 'plan_name_snapshot', 'created_at')
    search_fields = ('purchase_id', 'user__email', 'user__user_id')
    readonly_fields = (
        'purchase_id',
        'plan_name_snapshot',
        'investment_amount',
        'target_amount',
        'daily_rate_snapshot',
        'created_at',
        'updated_at',
    )


@admin.register(VIPReward)
class VIPRewardAdmin(admin.ModelAdmin):
    list_display = (
        'reward_id',
        'user',
        'vip_purchase',
        'reward_date',
        'calculated_amount',
        'credited_amount',
        'status',
    )
    list_filter = ('status', 'reward_date')
    search_fields = ('reward_id', 'user__email', 'user__user_id')
    readonly_fields = ('reward_id', 'created_at', 'updated_at')
