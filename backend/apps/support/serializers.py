"""Support API serializers (Section 11)."""

from rest_framework import serializers

from .models import SupportConversation, SupportMessage


class SupportMessageSerializer(serializers.ModelSerializer):
    """Thread message — plain text only; sender shown as role, not account."""

    sender_type = serializers.SerializerMethodField()

    class Meta:
        model = SupportMessage
        fields = ['id', 'sender_type', 'message', 'created_at']
        read_only_fields = fields

    def get_sender_type(self, obj) -> str:
        return 'support' if obj.is_admin else 'user'


class SupportConversationListSerializer(serializers.ModelSerializer):
    """List row: id, subject, status, timestamps, last-message preview (§28)."""

    last_message_preview = serializers.SerializerMethodField()
    last_message_at = serializers.SerializerMethodField()

    class Meta:
        model = SupportConversation
        fields = [
            'conversation_id',
            'subject',
            'status',
            'created_at',
            'updated_at',
            'last_message_at',
            'last_message_preview',
        ]
        read_only_fields = fields

    def get_last_message_preview(self, obj) -> str:
        row = getattr(obj, 'last_message', None)
        if row is None:
            return ''
        preview = ' '.join(row.message.split())
        return preview[:120] + ('…' if len(preview) > 120 else '')

    def get_last_message_at(self, obj) -> object:
        row = getattr(obj, 'last_message', None)
        return row.created_at if row else None


class SupportConversationDetailSerializer(serializers.ModelSerializer):
    """Detail payload with the full (capped) message thread (§34, §40)."""

    messages = serializers.SerializerMethodField()

    class Meta:
        model = SupportConversation
        fields = [
            'conversation_id',
            'subject',
            'status',
            'created_at',
            'updated_at',
            'closed_at',
            'messages',
        ]
        read_only_fields = fields

    def get_messages(self, obj) -> list:
        rows = obj.messages.all()[:200]  # hard cap; §40
        return SupportMessageSerializer(rows, many=True).data


class NewConversationSerializer(serializers.Serializer):
    """POST /api/support/conversations/ payload (§30–§31)."""

    subject = serializers.CharField(max_length=200, required=True)
    message = serializers.CharField(max_length=5000, required=True)


class NewMessageSerializer(serializers.Serializer):
    """POST /api/support/conversations/<id>/messages/ payload (§35)."""

    message = serializers.CharField(max_length=5000, required=True)
