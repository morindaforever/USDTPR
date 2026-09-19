"""Admin registration for support app."""

from django.contrib import admin

from .models import SupportConversation, SupportMessage


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ('created_at',)


@admin.register(SupportConversation)
class SupportConversationAdmin(admin.ModelAdmin):
    list_display = ('conversation_id', 'user', 'subject', 'status', 'priority', 'created_at', 'closed_at')
    list_filter = ('status', 'priority', 'created_at')
    search_fields = ('conversation_id', 'subject', 'user__email', 'user__user_id')
    readonly_fields = ('conversation_id', 'created_at', 'updated_at')
    inlines = [SupportMessageInline]


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'is_admin', 'created_at')
    list_filter = ('is_admin', 'created_at')
    search_fields = ('message', 'sender__email')
    readonly_fields = ('created_at',)
