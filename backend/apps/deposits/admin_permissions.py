"""Shared admin permission for the admin API surface."""

from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    """Allow only authenticated staff users (Django is_staff flag)."""

    message = 'Admin privileges are required for this action.'

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_staff)
