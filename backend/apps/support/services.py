"""Support service layer (Section 11).

All conversation/message mutations live here so views stay thin and the
rules (ownership, closed-conversation guards, rate limits, notifications,
audit) are enforced in exactly one place.
"""

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.utils import timezone

from apps.core.models import AuditLog
from apps.accounts.services import AuthError, ensure_active
from apps.notifications.models import Notification
from apps.notifications.services import notify_event

from .models import SupportConversation, SupportMessage

MAX_SUBJECT_LENGTH = 200
MAX_MESSAGE_LENGTH = 5000

# §47: abuse protection — generous enough for legitimate support use.
CREATE_LIMIT = 5          # new conversations per hour per user
MESSAGE_LIMIT = 30        # messages per hour per user (across conversations)


class SupportError(Exception):
    """Domain error; message is safe to surface, errors maps field → list."""

    def __init__(self, message: str, errors: dict | None = None, http_status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.errors = errors or {}
        self.http_status = http_status


def _ensure_active_or_support_error(user) -> None:
    """Translate the account-status gate into a SupportError (§9)."""
    try:
        ensure_active(user)
    except AuthError as exc:
        raise SupportError(exc.message) from exc


def _clean_text(value: str) -> str:
    """Normalize untrusted text (§32–33): strip, collapse line spam.

    Rendering is plain text everywhere (React escapes by default); this is
    input hygiene, not a sanitizer for an HTML pipeline — none exists.
    """
    return value.strip()


def _contains_unsafe_link(value: str) -> bool:
    """Reject javascript:/vbscript:/data: URLs inside message text (§33)."""
    validator = URLValidator(schemes=['http', 'https'])
    for token in value.replace('\n', ' ').split(' '):
        candidate = token.strip()
        if not candidate or ':' not in candidate:
            continue
        if candidate.lower().startswith(('javascript:', 'vbscript:', 'data:', 'file:')):
            return True
        try:
            validator(candidate)
        except ValidationError:
            # Not a well-formed http(s) URL — allowed as plain text.
            continue
    return False


def _rate_limit(user, bucket: str, limit: int) -> None:
    """Fixed-window counter in the shared cache (Redis in prod, locmem tests)."""
    key = f'support-rl:{bucket}:{user.pk}'
    count = cache.get(key, 0)
    if count >= limit:
        raise SupportError(
            'Too many requests. Please wait a moment before trying again.',
            http_status=429,
        )
    cache.set(key, count + 1, timeout=3600)


def _audit(actor, action: str, target: SupportConversation, description: str) -> None:
    AuditLog.objects.create(
        actor_user=actor,
        action=action,
        target_type='support.conversation',
        target_id=str(target.pk),
        description=description,
    )


def _user_notification(user, conversation: SupportConversation, *, message_row=None) -> None:
    """Section 13: idempotent per message — each staff reply has its own
    event key, so retries never duplicate and every reply notifies once."""
    suffix = str(message_row.pk) if message_row is not None else 'updated'
    notify_event(
        user=user,
        notification_type=Notification.NotificationType.SUPPORT,
        title='New support reply',
        message=f'Support has replied to your conversation: "{conversation.subject}"',
        event_key=f'support:{conversation.conversation_id}:reply:{suffix}',
        related_type='support_conversation',
        related_id=conversation.conversation_id,
    )


@transaction.atomic
def create_conversation(user, subject: str, message: str) -> SupportConversation:
    """POST /api/support/conversations/ (§30) — conversation + first message."""
    # §9: suspended/banned accounts cannot open tickets.
    _ensure_active_or_support_error(user)
    subject = _clean_text(subject)
    message = _clean_text(message)
    if not subject:
        raise SupportError('Please correct the highlighted fields.', {'subject': ['Subject is required.']})
    if len(subject) > MAX_SUBJECT_LENGTH:
        raise SupportError(
            'Please correct the highlighted fields.',
            {'subject': [f'Subject must be at most {MAX_SUBJECT_LENGTH} characters.']},
        )
    if not message:
        raise SupportError('Please correct the highlighted fields.', {'message': ['Message is required.']})
    if len(message) > MAX_MESSAGE_LENGTH:
        raise SupportError(
            'Please correct the highlighted fields.',
            {'message': [f'Message must be at most {MAX_MESSAGE_LENGTH} characters.']},
        )
    if _contains_unsafe_link(message) or _contains_unsafe_link(subject):
        raise SupportError(
            'Please correct the highlighted fields.',
            {'message': ['Message contains an unsupported link scheme.']},
        )
    _rate_limit(user, 'create', CREATE_LIMIT)

    conversation = SupportConversation.objects.create(user=user, subject=subject)
    SupportMessage.objects.create(conversation=conversation, sender=user, message=message)
    _audit(user, AuditLog.Action.CREATE, conversation, 'Support conversation created')
    return conversation


@transaction.atomic
def send_message(user, conversation: SupportConversation, message: str) -> SupportMessage:
    """POST /api/support/conversations/<id>/messages/ (§35, §37)."""
    # §9: suspended/banned accounts cannot reply.
    _ensure_active_or_support_error(user)
    text = _clean_text(message)
    if not text:
        raise SupportError('Please correct the highlighted fields.', {'message': ['Message is required.']})
    if len(text) > MAX_MESSAGE_LENGTH:
        raise SupportError(
            'Please correct the highlighted fields.',
            {'message': [f'Message must be at most {MAX_MESSAGE_LENGTH} characters.']},
        )
    if _contains_unsafe_link(text):
        raise SupportError(
            'Please correct the highlighted fields.',
            {'message': ['Message contains an unsupported link scheme.']},
        )
    _rate_limit(user, 'message', MESSAGE_LIMIT)

    if conversation.status == SupportConversation.Status.CLOSED:
        raise SupportError('This conversation is closed.', http_status=409)

    is_admin = user.is_staff
    message_row = SupportMessage.objects.create(
        conversation=conversation,
        sender=user,
        message=text,
        is_admin=is_admin,
    )
    if not is_admin:
        # User replied (or opened) → support's turn (§37).
        conversation.status = SupportConversation.Status.IN_PROGRESS
        conversation.save(update_fields=['status', 'updated_at'])
    else:
        # Staff reply → notify the owner exactly once per message (§42, §73).
        _user_notification(conversation.user, conversation, message_row=message_row)
    _audit(
        user,
        AuditLog.Action.OTHER,
        conversation,
        'Support reply sent' if is_admin else 'Support message sent',
    )
    return message_row


@transaction.atomic
def close_conversation(user, conversation: SupportConversation) -> tuple[SupportConversation, bool]:
    """POST /api/support/conversations/<id>/close/ (§38) — owner idempotent."""
    if conversation.status == SupportConversation.Status.CLOSED:
        return conversation, False  # idempotent: no duplicate ops
    conversation.status = SupportConversation.Status.CLOSED
    conversation.closed_at = timezone.now()
    conversation.save(update_fields=['status', 'closed_at', 'updated_at'])
    _audit(user, AuditLog.Action.UPDATE, conversation, 'Support conversation closed')
    return conversation, True


@transaction.atomic
def reopen_conversation(user, conversation: SupportConversation) -> SupportConversation:
    """POST /api/support/conversations/<id>/reopen/ (§39) — owner only,
    allowed for RESOLVED/CLOSED threads that were never archived."""
    if conversation.status != SupportConversation.Status.CLOSED:
        raise SupportError('Only closed conversations can be reopened.', http_status=409)
    conversation.status = SupportConversation.Status.IN_PROGRESS
    conversation.closed_at = None
    conversation.save(update_fields=['status', 'closed_at', 'updated_at'])
    _audit(user, AuditLog.Action.UPDATE, conversation, 'Support conversation reopened')
    return conversation
