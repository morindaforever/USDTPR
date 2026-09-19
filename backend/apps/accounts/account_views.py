"""Account API views (Section 11).

User-facing surface over the Section 3 authentication services. The
authenticated user is ALWAYS ``request.user`` — no identifier is accepted
from the client (§9). Raw AuditLog rows are never returned; the activity
feed is a curated, safe projection (§19–20).
"""

from django.contrib.auth import update_session_auth_hash
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler
from apps.core.models import AuditLog

from .models import LoginActivity
from .account_serializers import (
    AccountActivitySerializer,
    PasswordChangeSerializer,
    ProfileUpdateSerializer,
)
from .services import (
    change_password as change_password_service,
    record_login_activity,
)
from .serializers import UserPublicSerializer


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

    def _fail(self, message, errors=None, http_status=400):
        return Response(
            {'success': False, 'message': message, 'errors': errors or {}},
            status=http_status,
        )


class AccountMeView(_AuthedAPIView):
    """GET /api/account/me/ — same safe shape as /api/auth/me/ (§50)."""

    def get(self, request):
        return self._envelope({'user': UserPublicSerializer(request.user).data})


class ProfileView(_AuthedAPIView):
    """GET + PATCH /api/account/profile/ (§7–§9)."""

    def get(self, request):
        return self._envelope({'user': UserPublicSerializer(request.user).data})

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user, data=request.data, partial=True, context={'request': request},
        )
        if not serializer.is_valid():
            return self._fail('Please correct the highlighted fields.', serializer.errors)
        serializer.save()
        AuditLog.objects.create(
            actor_user=request.user,
            action=AuditLog.Action.UPDATE,
            target_type='account.profile',
            target_id=request.user.user_id,
            description='User updated profile fields: ' + ', '.join(sorted(serializer.validated_data)),
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
        )
        return self._envelope(
            {'user': UserPublicSerializer(request.user).data},
            message='Profile updated.',
        )


class ChangePasswordView(_AuthedAPIView):
    """POST /api/account/change-password/ (§14–§16).

    Reuses the Section 3 ``change_password`` service (validators, hashing).
    On success every outstanding refresh token is blacklisted so old sessions
    cannot silently persist, and an audit row WITHOUT any password material
    is written (§56).
    """

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return self._fail('Please correct the highlighted fields.', serializer.errors)
        attrs = serializer.validated_data
        change_password_service(request.user, attrs['current_password'], attrs['new_password'])

        from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

        blacklisted = 0
        for token in OutstandingToken.objects.filter(user=request.user):
            from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken

            _, created = BlacklistedToken.objects.get_or_create(token=token)
            if created:
                blacklisted += 1
        update_session_auth_hash(request, request.user)

        AuditLog.objects.create(
            actor_user=request.user,
            action=AuditLog.Action.UPDATE,
            target_type='account.password',
            target_id=request.user.user_id,
            description='Password changed; refresh tokens invalidated.',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')[:512],
        )
        record_login_activity(request.user, LoginActivity.Outcome.SUCCESS, request, detail='password changed')
        return self._envelope(message='Password updated successfully.')


class AccountActivityView(_AuthedAPIView):
    """GET /api/account/activity/ — safe, curated activity feed (§19–20).

    Combines three internal sources into user-facing entries; raw AuditLog /
    LoginActivity fields (IPs, user agents, target ids) are never exposed.
    """

    LIMIT = 50

    def get(self, request):
        entries: list[dict] = []

        logins = LoginActivity.objects.filter(
            user=request.user, outcome=LoginActivity.Outcome.SUCCESS,
        ).order_by('-created_at')[: self.LIMIT]
        for row in logins:
            detail = 'password change' if 'password' in row.detail else 'login'
            entries.append({
                'type': 'login',
                'title': 'Signed in' if detail == 'login' else 'Password changed',
                'detail': detail,
                'occurred_at': row.created_at,
            })

        profiles = AuditLog.objects.filter(
            actor_user=request.user,
            action=AuditLog.Action.UPDATE,
        ).filter(Q(target_type='account.profile') | Q(target_type='account.password'))[
            : self.LIMIT
        ]
        for row in profiles:
            if row.target_type == 'account.password':
                continue  # already represented by the LoginActivity entry
            entries.append({
                'type': 'profile_update',
                'title': 'Profile updated',
                'detail': '',
                'occurred_at': row.created_at,
            })

        from apps.deposits.models import Deposit
        from apps.vip.models import VIPPurchase, VIPReward
        from apps.withdrawals.models import Withdrawal

        deposits = Deposit.objects.filter(user=request.user).order_by('-created_at')[:20]
        for d in deposits:
            entries.append({
                'type': 'deposit',
                'title': 'Deposit request submitted',
                'detail': str(d.amount),
                'occurred_at': d.created_at,
            })
        withdrawals = Withdrawal.objects.filter(user=request.user).order_by('-created_at')[:20]
        for w in withdrawals:
            entries.append({
                'type': 'withdrawal',
                'title': f'Withdrawal {w.status.lower()}',
                'detail': str(w.requested_amount),
                'occurred_at': w.created_at,
            })
        purchases = VIPPurchase.objects.filter(user=request.user).order_by('-created_at')[:20]
        for p in purchases:
            entries.append({
                'type': 'vip_purchase',
                'title': f'VIP plan activated: {p.plan_name_snapshot}',
                'detail': str(p.investment_amount),
                'occurred_at': p.created_at,
            })
        rewards = VIPReward.objects.filter(user=request.user).order_by('-created_at')[:20]
        for r in rewards:
            entries.append({
                'type': 'reward',
                'title': 'Mining reward credited',
                'detail': str(r.credited_amount),
                'occurred_at': r.created_at,
            })

        entries.sort(key=lambda e: e['occurred_at'], reverse=True)
        entries = entries[: self.LIMIT]
        return self._envelope({'results': AccountActivitySerializer(entries, many=True).data})


__all__ = [
    'AccountActivityView',
    'AccountMeView',
    'ChangePasswordView',
    'ProfileView',
]
