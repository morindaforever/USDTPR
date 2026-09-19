"""Admin user management (Section 12 §10–§17, §71).

Status changes are the ONLY writable fields — every action is explicit,
reason-required for suspend/ban, audited, notification-producing, and
idempotent. Mass-assignment surface is zero: no generic update endpoint
exists (§71, §100–101).
"""

from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.accounts.models import LoginActivity
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.wallet.pagination import EnvelopePagination

from .permissions import GroupPermission
from .serializers import (
    AdminUserActionSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
)
from .views import AdminAPIView, envelope, error_envelope

User = get_user_model()

STATUS_TITLES = {
    'ACTIVE': 'Account activated',
    'SUSPENDED': 'Account suspended',
    'BANNED': 'Account banned',
}
STATUS_BODIES = {
    'ACTIVE': 'Your account has been reactivated. Welcome back!',
    'SUSPENDED': 'Your account has been suspended. Contact support for assistance.',
    'BANNED': 'Your account has been banned for violating platform rules.',
}


class AdminUserListCreateView(AdminAPIView):
    """GET /api/admin/users/?search=&status=&page=&page_size= (§11–13)."""

    def get(self, request):
        qs = User.objects.order_by('-created_at')
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(user_id__iexact=search)
                | Q(full_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
        status_filter = (request.query_params.get('status') or '').strip().upper()
        if status_filter and status_filter in User.AccountStatus.values:
            qs = qs.filter(account_status=status_filter)
        staff_filter = (request.query_params.get('staff') or '').strip().lower()
        if staff_filter in ('true', '1'):
            qs = qs.filter(is_staff=True)
        elif staff_filter in ('false', '0'):
            qs = qs.filter(is_staff=False)

        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AdminUserListSerializer(page, many=True).data)


class AdminUserDetailView(AdminAPIView):
    """GET /api/admin/users/<user_id>/ — read-only profile + wallet (§14)."""

    def get(self, request, user_id: str):
        user = User.objects.filter(user_id=user_id).select_related('wallet').first()
        if user is None:
            return error_envelope('User not found.', http_status=404)
        return envelope(AdminUserDetailSerializer(user).data)


class AdminUserKycView(AdminAPIView):
    """POST /api/admin/users/<user_id>/kyc/  body: {action, reason}

    Conversion §17: the admin can mark a verification as PENDING (a real
    provider session started) or REJECTED, but NEVER approve directly —
    ``APPROVED`` is set only by an actual identity-provider verification
    event (apps.integrations.compliance). While no provider is configured
    the verification remains pending and withdrawal-KYC enforcement stays
    disabled (KYC_REQUIRED_FOR_WITHDRAWALS=False).
    """

    required_groups = ('User Managers',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def post(self, request, user_id: str):
        user = User.objects.filter(user_id=user_id).first()
        if user is None:
            return error_envelope('User not found.', http_status=404)

        action = ((request.data or {}).get('action') or '').strip().lower()
        reason = ((request.data or {}).get('reason') or '').strip()
        if action == 'pending':
            new_status, audit = User.KYCStatus.PENDING, 'Verification session marked pending.'
        elif action == 'reject':
            if not reason:
                return error_envelope('A rejection reason is required.', http_status=400)
            new_status, audit = User.KYCStatus.REJECTED, f'Verification rejected. Reason: {reason}'
        elif action == 'approve':
            return error_envelope(
                'KYC approval can only be recorded by a real identity-verification '
                'provider event — it cannot be set manually.',
                http_status=409,
            )
        else:
            return error_envelope('Unknown action.', http_status=400)

        with db_transaction.atomic():
            user.kyc_status = new_status
            user.kyc_verified_at = timezone.now() if new_status == User.KYCStatus.APPROVED else None
            user.save(update_fields=['kyc_status', 'kyc_verified_at', 'updated_at'])
            AuditLog.objects.create(
                actor_user=request.user,
                action=AuditLog.Action.UPDATE,
                target_type='admin.user_kyc',
                target_id=user.user_id,
                description=audit,
                ip_address=request.META.get('REMOTE_ADDR'),
            )
        return envelope({'user_id': user.user_id, 'kyc_status': user.kyc_status})

    def get(self, request, user_id: str):
        user = User.objects.filter(user_id=user_id).first()
        if user is None:
            return error_envelope('User not found.', http_status=404)
        return envelope({'user_id': user.user_id, 'kyc_status': user.kyc_status})


# timezone is imported at module scope in this module's existing imports
from django.utils import timezone  # noqa: E402  (kept beside usage for clarity)


class AdminUserStatusView(AdminAPIView):
    """POST /api/admin/users/<user_id>/status/  body: {action, reason}

    action ∈ activate | suspend | ban. Requires the User Managers group
    (superusers exempt). Idempotent: applying the current status again
    returns the existing state without a duplicate audit/notification.
    """

    required_groups = ('User Managers',)
    permission_classes = [IsAuthenticated, GroupPermission]

    ACTIONS = {
        'activate': User.AccountStatus.ACTIVE,
        'suspend': User.AccountStatus.SUSPENDED,
        'ban': User.AccountStatus.BANNED,
    }

    def post(self, request, user_id: str):
        user = User.objects.filter(user_id=user_id).first()
        if user is None:
            return error_envelope('User not found.', http_status=404)

        serializer = AdminUserActionSerializer(
            data=request.data, context={'action': (request.data or {}).get('action')},
        )
        if not serializer.is_valid():
            return error_envelope('Please correct the highlighted fields.', serializer.errors)
        action = (request.data or {}).get('action')
        if action not in self.ACTIONS:
            return error_envelope('Unknown action.', http_status=404)
        target_status = self.ACTIONS[action]
        reason = (serializer.validated_data.get('reason') or '').strip()

        if user.is_superuser and target_status != User.AccountStatus.ACTIVE:
            return error_envelope('Superuser accounts cannot be suspended or banned.', http_status=409)

        if user.account_status == target_status:
            return envelope(
                AdminUserDetailSerializer(
                    User.objects.filter(pk=user.pk).select_related('wallet').first()
                ).data,
                message=f'User is already {target_status.lower()}.',
            )

        old_status = user.account_status
        with db_transaction.atomic():
            user.account_status = target_status
            user.save(update_fields=['account_status', 'updated_at'])
            if target_status != User.AccountStatus.ACTIVE:
                self._blacklist_sessions(user)
            AuditLog.objects.create(
                actor_user=request.user,
                action=AuditLog.Action.UPDATE,
                target_type='admin.user_status',
                target_id=user.user_id,
                description=f'Status {old_status} → {target_status}. Reason: {reason or "(none provided)"}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
            )
            Notification.objects.create(
                user=user,
                notification_type=Notification.NotificationType.SYSTEM,
                title=STATUS_TITLES[target_status],
                message=STATUS_BODIES[target_status],
            )
        return envelope(
            AdminUserDetailSerializer(
                User.objects.filter(pk=user.pk).select_related('wallet').first()
            ).data,
            message=f'User {action}d.',
        )

    @staticmethod
    def _blacklist_sessions(user) -> None:
        """Kill refresh tokens so a suspended/banned session cannot persist."""
        try:
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken, OutstandingToken,
            )

            for token in OutstandingToken.objects.filter(user=user):
                BlacklistedToken.objects.get_or_create(token=token)
        except Exception:  # pragma: no cover - blacklist app always installed
            pass


class AdminUserHistoryView(AdminAPIView):
    """GET /api/admin/users/<user_id>/history/ — read-only summaries.

    Query param ``type`` selects: deposits | withdrawals | vip | rewards |
    commissions | support | logins | audit. Returns capped lists (§14).
    """

    CAP = 50

    def get(self, request, user_id: str):
        user = User.objects.filter(user_id=user_id).first()
        if user is None:
            return error_envelope('User not found.', http_status=404)
        kind = (request.query_params.get('type') or 'deposits').lower()

        from apps.deposits.models import Deposit
        from apps.referrals.models import ReferralCommission
        from apps.support.models import SupportConversation
        from apps.vip.models import VIPPurchase, VIPReward
        from apps.withdrawals.models import Withdrawal

        def rows(qs, serializer, many=True):
            return {'results': serializer(qs, many=many).data}

        if kind == 'deposits':
            from apps.deposits.serializers import DepositSerializer

            return envelope(rows(
                Deposit.objects.filter(user=user).order_by('-created_at')[: self.CAP],
                DepositSerializer,
            ))
        if kind == 'withdrawals':
            from apps.withdrawals.serializers import WithdrawalAdminSerializer

            return envelope(rows(
                Withdrawal.objects.filter(user=user).order_by('-created_at')[: self.CAP],
                WithdrawalAdminSerializer,
            ))
        if kind == 'vip':
            from .serializers import AdminVIPPurchaseSerializer

            return envelope(rows(
                VIPPurchase.objects.filter(user=user).order_by('-created_at')[: self.CAP],
                AdminVIPPurchaseSerializer,
            ))
        if kind == 'rewards':
            from .serializers import AdminVIPRewardSerializer

            return envelope(rows(
                VIPReward.objects.filter(user=user).order_by('-created_at')[: self.CAP],
                AdminVIPRewardSerializer,
            ))
        if kind == 'commissions':
            from .serializers import AdminCommissionSerializer

            return envelope(rows(
                ReferralCommission.objects.filter(user=user).order_by('-created_at')[: self.CAP],
                AdminCommissionSerializer,
            ))
        if kind == 'support':
            from .serializers import AdminSupportConversationListSerializer

            return envelope(rows(
                SupportConversation.objects.filter(user=user).order_by('-updated_at')[: self.CAP],
                AdminSupportConversationListSerializer,
            ))
        if kind == 'logins':
            data = [
                {
                    'outcome': r.outcome,
                    'ip_address': r.ip_address,
                    'detail': r.detail,
                    'created_at': r.created_at,
                }
                for r in LoginActivity.objects.filter(user=user).order_by('-created_at')[: self.CAP]
            ]
            return envelope({'results': data})
        if kind == 'audit':
            from .serializers import AdminAuditLogSerializer

            return envelope(rows(
                AuditLog.objects.filter(
                    Q(actor_user=user) | Q(target_id=user.user_id)
                ).order_by('-created_at')[: self.CAP],
                AdminAuditLogSerializer,
            ))
        return error_envelope('Unknown history type.', http_status=404)
