"""Admin permission classes (Section 12 §65–66).

Base gate: ``IsAdminUser`` (is_staff) — reused from the deposits app.

Least-privilege gates for dangerous actions: superusers always pass; staff
users must belong to a Django group whose name is listed for the action.
``bootstrap_admin_groups`` (management command) creates the standard groups
so operators never hand-edit permission rows.
"""

from rest_framework.permissions import BasePermission

from apps.deposits.admin_permissions import IsAdminUser  # noqa: F401 (re-export)

__all__ = ['IsAdminUser', 'GroupPermission']


class GroupPermission(BasePermission):
    """Allow superusers, or staff members in ANY of ``required_groups``.

    Views declare ``required_groups = ['Support Agents']`` etc. This keeps
    the principle of least privilege without inventing a parallel permission
    system — plain Django groups.
    """

    message = 'You do not have permission to perform this action.'

    #: Overridden per-view.
    required_groups: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.is_staff):
            return False
        if user.is_superuser:
            return True
        required = getattr(view, 'required_groups', self.required_groups)
        if not required:
            return True  # no extra groups declared → staff is enough
        return user.groups.filter(name__in=required).exists()
