"""Support conversations and messages (chat UI arrives in a later section)."""

from django.conf import settings
from django.db import models

from apps.core.db import HumanIDField, TimeStampedModel


class SupportConversation(TimeStampedModel):
    """A user's support thread."""

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        CLOSED = 'CLOSED', 'Closed'

    class Priority(models.TextChoices):
        LOW = 'LOW', 'Low'
        NORMAL = 'NORMAL', 'Normal'
        HIGH = 'HIGH', 'High'
        URGENT = 'URGENT', 'Urgent'

    conversation_id = HumanIDField(prefix='SUP', padding=8)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='support_conversations',
    )
    subject = models.CharField(max_length=200)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN, db_index=True)
    priority = models.CharField(max_length=8, choices=Priority.choices, default=Priority.NORMAL)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['user', '-updated_at']),
            models.Index(fields=['status', '-updated_at']),
        ]

    def __str__(self) -> str:
        return f'{self.conversation_id}: {self.subject}'


class SupportMessage(models.Model):
    """A single message inside a conversation."""

    conversation = models.ForeignKey(
        SupportConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='support_messages',
    )
    message = models.TextField()
    is_admin = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self) -> str:
        author = 'admin' if self.is_admin else self.sender
        return f'{self.conversation_id}: {author}: {self.message[:32]}'
