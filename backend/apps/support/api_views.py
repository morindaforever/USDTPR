"""Support API views (Section 11 §51).

Every endpoint requires authentication and filters by ``request.user`` —
the owner check IS the IDOR protection (§52–§53): a foreign conversation id
produces a 404 with the same shape as a missing one, never a leak.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler
from apps.wallet.pagination import EnvelopePagination

from .models import SupportConversation
from .serializers import (
    NewConversationSerializer,
    NewMessageSerializer,
    SupportConversationDetailSerializer,
    SupportConversationListSerializer,
)
from . import services


def _exception_context(view) -> dict:
    return {'view': view, 'request': getattr(view, 'request', None), 'args': (), 'kwargs': {}}


class _AuthedAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response

    def _envelope(self, data=None, message='OK', http_status=200):
        body = {'success': True, 'message': message}
        if data is not None:
            body['data'] = data
        return Response(body, status=http_status)

    def _fail(self, exc: services.SupportError):
        return Response(
            {'success': False, 'message': exc.message, 'errors': exc.errors},
            status=exc.http_status,
        )


def _owner_conversation(user, conversation_id: str):
    """Owner-scoped fetch; anything else is 404 (§53)."""
    return (
        SupportConversation.objects.filter(user=user, conversation_id=conversation_id).first()
    )


class SupportConversationListCreateView(_AuthedAPIView):
    """GET (paginated, filterable) + POST /api/support/conversations/ (§40–41)."""

    def get(self, request):
        qs = SupportConversation.objects.filter(user=request.user)
        status_filter = request.query_params.get('status')
        if status_filter:
            wanted = [s.strip().upper() for s in status_filter.split(',') if s.strip()]
            valid = [s for s in wanted if s in SupportConversation.Status.values]
            if valid:
                qs = qs.filter(status__in=valid)
        qs = qs.prefetch_related('messages')
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            SupportConversationListSerializer(page, many=True).data
        )

    def post(self, request):
        serializer = NewConversationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Please correct the highlighted fields.',
                 'errors': serializer.errors},
                status=400,
            )
        try:
            conversation = services.create_conversation(
                request.user,
                serializer.validated_data['subject'],
                serializer.validated_data['message'],
            )
        except services.SupportError as exc:
            return self._fail(exc)
        return self._envelope(
            SupportConversationDetailSerializer(conversation).data,
            message='Support conversation created.',
            http_status=201,
        )


class SupportConversationDetailView(_AuthedAPIView):
    """GET /api/support/conversations/<conversation_id>/ (§34)."""

    def get(self, request, conversation_id: str):
        conversation = _owner_conversation(request.user, conversation_id)
        if conversation is None:
            return Response(
                {'success': False, 'message': 'Conversation not found.', 'errors': {}},
                status=404,
            )
        return self._envelope(SupportConversationDetailSerializer(conversation).data)


class SupportMessageCreateView(_AuthedAPIView):
    """POST /api/support/conversations/<conversation_id>/messages/ (§35–§37)."""

    def post(self, request, conversation_id: str):
        conversation = _owner_conversation(request.user, conversation_id)
        if conversation is None:
            return Response(
                {'success': False, 'message': 'Conversation not found.', 'errors': {}},
                status=404,
            )
        serializer = NewMessageSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'success': False, 'message': 'Please correct the highlighted fields.',
                 'errors': serializer.errors},
                status=400,
            )
        try:
            services.send_message(request.user, conversation, serializer.validated_data['message'])
        except services.SupportError as exc:
            return self._fail(exc)
        conversation.refresh_from_db()
        return self._envelope(
            SupportConversationDetailSerializer(conversation).data,
            message='Message sent.',
            http_status=201,
        )


class SupportConversationCloseView(_AuthedAPIView):
    """POST /api/support/conversations/<conversation_id>/close/ (§38)."""

    def post(self, request, conversation_id: str):
        conversation = _owner_conversation(request.user, conversation_id)
        if conversation is None:
            return Response(
                {'success': False, 'message': 'Conversation not found.', 'errors': {}},
                status=404,
            )
        try:
            conversation, closed = services.close_conversation(request.user, conversation)
        except services.SupportError as exc:
            return self._fail(exc)
        return self._envelope(
            SupportConversationDetailSerializer(conversation).data,
            message='Conversation closed.' if closed else 'Conversation was already closed.',
        )


class SupportConversationReopenView(_AuthedAPIView):
    """POST /api/support/conversations/<conversation_id>/reopen/ (§39)."""

    def post(self, request, conversation_id: str):
        conversation = _owner_conversation(request.user, conversation_id)
        if conversation is None:
            return Response(
                {'success': False, 'message': 'Conversation not found.', 'errors': {}},
                status=404,
            )
        try:
            conversation = services.reopen_conversation(request.user, conversation)
        except services.SupportError as exc:
            return self._fail(exc)
        return self._envelope(
            SupportConversationDetailSerializer(conversation).data,
            message='Conversation reopened.',
        )


__all__ = [
    'SupportConversationCloseView',
    'SupportConversationDetailView',
    'SupportConversationListCreateView',
    'SupportConversationReopenView',
    'SupportMessageCreateView',
]
