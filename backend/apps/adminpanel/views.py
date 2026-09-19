"""Admin panel API base (Section 12).

Shared helpers for every admin view module; the concrete endpoints live in
``dashboard_views`` / ``user_views`` / etc., all mounted under
``/api/admin/`` via ``adminpanel.urls``.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler

from .permissions import GroupPermission, IsAdminUser

__all__ = ['AdminAPIView', 'envelope', 'error_envelope', 'IsAdminUser', 'GroupPermission']


def envelope(data=None, message: str = 'OK', http_status: int = 200) -> Response:
    body = {'success': True, 'message': message}
    if data is not None:
        body['data'] = data
    return Response(body, status=http_status)


def error_envelope(message: str, errors: dict | None = None, http_status: int = 400) -> Response:
    return Response(
        {'success': False, 'message': message, 'errors': errors or {}},
        status=http_status,
    )


class AdminAPIView(APIView):
    """Base for admin endpoints: authenticated staff required (§2–3)."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def handle_exception(self, exc):
        response = api_exception_handler(
            exc, {'view': self, 'request': getattr(self, 'request', None), 'args': (), 'kwargs': {}}
        )
        if response is None:
            raise exc
        return response
