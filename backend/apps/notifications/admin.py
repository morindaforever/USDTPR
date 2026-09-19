"""Admin registration for notifications."""

from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'notification_type', 'title', 'is_read', 'created_at', 'read_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__email', 'user__user_id')
    readonly_fields = ('created_at', 'read_at')
