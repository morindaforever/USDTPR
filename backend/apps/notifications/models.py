"""User notifications."""

from django.conf import settings
from django.db import models


class Notification(models.Model):
    """In-app notification for a user.

    Section 13 additions: ``related_type``/``related_id`` point at the
    source record (deposit, withdrawal, …) for deep links, and
    ``event_key`` makes financial-event notifications idempotent — a
    duplicate event (reward retry, replayed webhook, worker retry) can
    never create a second notification.
    """

    class NotificationType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        WITHDRAWAL = 'WITHDRAWAL', 'Withdrawal'
        VIP = 'VIP', 'VIP'
        REWARD = 'REWARD', 'Reward'
        REFERRAL = 'REFERRAL', 'Referral'
        SUPPORT = 'SUPPORT', 'Support'
        SECURITY = 'SECURITY', 'Security'
        ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'
        SYSTEM = 'SYSTEM', 'System'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=16, choices=NotificationType.choices, db_index=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_type = models.CharField(max_length=64, blank=True)
    related_id = models.CharField(max_length=64, blank=True, db_index=True)
    # Deterministic event key (e.g. reward:REW00000001:credited). Unique
    # per user when set — this is the idempotency guarantee.
    event_key = models.CharField(max_length=128, blank=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at']),
            models.Index(fields=['user', 'notification_type', '-created_at']),
            models.Index(fields=['user', 'event_key']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'event_key'],
                condition=~models.Q(event_key=''),
                name='uniq_notification_event_per_user',
            ),
        ]

    def __str__(self) -> str:
        return f'{self.notification_type}: {self.title}'
