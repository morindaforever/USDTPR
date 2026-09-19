"""Admin registration for core cross-cutting models.

AuditLog is intentionally read-only: the audit trail must not be editable.
"""

from django.contrib import admin

from .db import HumanIDCounter
from .models import AuditLog, CompanyValuation, SiteSetting


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'actor_user', 'action', 'target_type', 'target_id', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('description', 'target_type', 'target_id', 'actor_user__email')
    readonly_fields = (
        'actor_user',
        'action',
        'target_type',
        'target_id',
        'description',
        'ip_address',
        'user_agent',
        'created_at',
    )
    date_hierarchy = 'created_at'

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'value', 'value_type', 'description', 'updated_at')
    search_fields = ('key', 'description')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CompanyValuation)
class CompanyValuationAdmin(admin.ModelAdmin):
    list_display = ('valuation_date', 'value', 'currency', 'is_demo', 'created_at')
    list_filter = ('is_demo', 'currency')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(HumanIDCounter)
class HumanIDCounterAdmin(admin.ModelAdmin):
    list_display = ('prefix', 'last_value')
    readonly_fields = ('prefix', 'last_value')

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
