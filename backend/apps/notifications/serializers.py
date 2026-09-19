"""Notification serializers (Section 13)."""

from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    type = serializers.CharField(source='notification_type', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id',
            'type',
            'title',
            'message',
            'related_type',
            'related_id',
            'is_read',
            'read_at',
            'created_at',
        ]
        read_only_fields = fields


__all__ = ['NotificationSerializer']
