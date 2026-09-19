"""User notification API (Section 13 §6–8).

Every queryset is scoped by ``request.user`` — other users' notifications
404 (no existence leak). Reuses the wallet app's EnvelopePagination and the
standard ``{success, message, data}`` envelope.

Endpoints:

    GET  /api/notifications/                 (?type=&is_read=&page=)
    GET  /api/notifications/unread-count/
    GET  /api/notifications/<id>/
    POST /api/notifications/<id>/read/       (idempotent)
    POST /api/notifications/read-all/
"""

from django.db.models import Q
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.wallet.pagination import EnvelopePagination

from .models import Notification
from .serializers import NotificationSerializer
from .services import mark_all_read as mark_all_read_service
from .services import mark_read as mark_read_service


def _error(message: str, http_status: int) -> Response:
    return Response(
        {'success': False, 'message': message, 'errors': {}},
        status=http_status,
    )


class NotificationListView(ListAPIView):
    """GET /api/notifications/ — own notifications, newest first (§7)."""

    serializer_class = NotificationSerializer
    pagination_class = EnvelopePagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Notification.objects.filter(user=self.request.user).order_by('-created_at', '-id')
        params = self.request.query_params
        ntype = params.get('type')
        if ntype:
            ntype = ntype.upper()
            valid = {choice for choice, _ in Notification.NotificationType.choices}
            if ntype not in valid:
                raise ValueError(f'Unknown notification type: {ntype}')
            qs = qs.filter(notification_type=ntype)
        is_read = params.get('is_read')
        if is_read is not None and is_read != '':
            if is_read.lower() not in ('true', 'false'):
                raise ValueError('is_read must be true or false.')
            qs = qs.filter(is_read=(is_read.lower() == 'true'))
        return qs

    def list(self, request, *args, **kwargs):
        try:
            response = super().list(request, *args, **kwargs)
        except ValueError:
            return _error('Invalid filter value.', 400)
        response.data['unread_count'] = Notification.objects.filter(
            user=request.user, is_read=False,
        ).count()
        return response

    def handle_exception(self, exc):
        if isinstance(exc, ValueError):
            return _error(str(exc), 400)
        return super().handle_exception(exc)


class UnreadCountView(APIView):
    """GET /api/notifications/unread-count/ — badge source (§29)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'success': True, 'message': 'OK', 'data': {'unread_count': count}})


class NotificationDetailView(RetrieveAPIView):
    """GET /api/notifications/<id>/ — own row only (§8 IDOR)."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    lookup_url_kwarg = 'notification_id'

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        try:
            instance = self.get_object()
        except (ValueError, Notification.DoesNotExist):
            return _error('Notification not found.', 404)
        return Response(
            {'success': True, 'message': 'OK', 'data': self.get_serializer(instance).data},
        )

    def handle_exception(self, exc):
        from rest_framework.exceptions import NotFound

        if isinstance(exc, (NotFound, Notification.DoesNotExist, ValueError)):
            return _error('Notification not found.', 404)
        return super().handle_exception(exc)


class NotificationReadView(APIView):
    """POST /api/notifications/<id>/read/ — idempotent mark-read (§5)."""

    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id: int):
        notification = (
            Notification.objects.filter(user=request.user, pk=notification_id).first()
        )
        if notification is None:
            return _error('Notification not found.', 404)
        mark_read_service(notification)
        return Response(
            {
                'success': True,
                'message': 'Notification marked as read.',
                'data': NotificationSerializer(notification).data,
            },
        )


class ReadAllView(APIView):
    """POST /api/notifications/read-all/ — idempotent bulk mark-read."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = mark_all_read_service(request.user)
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response(
            {
                'success': True,
                'message': 'All notifications marked as read.',
                'data': {'marked': updated, 'unread_count': count},
            },
        )


__all__ = [
    'NotificationDetailView',
    'NotificationListView',
    'NotificationReadView',
    'ReadAllView',
    'UnreadCountView',
]
