"""Centralized notification service (Section 13 §17).

The ONLY way application code creates notifications. Every helper is
idempotent via the ``event_key`` unique constraint: passing the same
deterministic key twice (reward retry, worker replay, double-click) can
never produce a duplicate row — the second write is a no-op.

Financial events follow the transaction-safety rule (§18): the caller
creates the notification INSIDE the same ``transaction.atomic`` block as
the financial change, so a rollback removes the notification too.
"""

from __future__ import annotations

from apps.notifications.models import Notification

__all__ = [
    'notify',
    'notify_event',
    'mark_read',
    'mark_all_read',
]


def notify(
    *,
    user,
    notification_type: str,
    title: str,
    message: str,
    related_type: str = '',
    related_id: str = '',
) -> Notification | None:
    """Create a notification. Plain text only — no HTML anywhere."""
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title=title[:200],
        message=message,
        related_type=related_type,
        related_id=str(related_id)[:64] if related_id else '',
    )


def notify_event(
    *,
    user,
    notification_type: str,
    title: str,
    message: str,
    event_key: str,
    related_type: str = '',
    related_id: str = '',
) -> Notification | None:
    """Idempotent variant: ``event_key`` uniquely identifies the event.

    Returns the existing row on replay (never a duplicate). Must be called
    inside the caller's transaction so rollback removes it with the finance
    change it describes (§18).
    """
    from django.db import IntegrityError, transaction

    try:
        with transaction.atomic():
            return Notification.objects.create(
                user=user,
                notification_type=notification_type,
                title=title[:200],
                message=message,
                related_type=related_type,
                related_id=str(related_id)[:64] if related_id else '',
                event_key=event_key,
            )
    except IntegrityError:
        # Same user + event_key already exists → replay, not an error.
        return Notification.objects.filter(user=user, event_key=event_key).first()


def mark_read(notification: Notification) -> Notification:
    """Mark one notification read. Idempotent (§5)."""
    if not notification.is_read:
        from django.utils import timezone

        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
    return notification


def mark_all_read(user) -> int:
    """Mark every unread notification for ``user`` read; returns count."""
    from django.utils import timezone

    unread = Notification.objects.filter(user=user, is_read=False)
    count = unread.count()
    unread.update(is_read=True, read_at=timezone.now())
    return count
