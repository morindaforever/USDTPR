"""Admin registration for accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ['-created_at']
    list_display = (
        'user_id',
        'email',
        'full_name',
        'phone',
        'referral_code',
        'referred_by',
        'account_status',
        'is_active',
        'created_at',
    )
    list_filter = ('account_status', 'is_active', 'is_staff', 'created_at')
    search_fields = ('user_id', 'email', 'phone', 'full_name', 'referral_code')
    readonly_fields = ('user_id', 'referral_code', 'created_at', 'updated_at', 'last_login')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Profile', {'fields': ('full_name', 'phone', 'referred_by')}),
        ('Identity', {'fields': ('user_id', 'referral_code')}),
        (
            'Status',
            {'fields': ('account_status', 'is_active', 'is_staff', 'is_superuser')},
        ),
        ('Timestamps', {'fields': ('created_at', 'updated_at', 'last_login')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'phone', 'password1', 'password2'),
            },
        ),
    )
