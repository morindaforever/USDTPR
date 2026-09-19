"""Admin operations views (Section 12 §40–§48, §52–§63).

Referrals/commissions are read-only (history is immutable). Support adds
staff reply + status transitions through the Section 11 service. Settings
edits always write an audit row; secrets never live in SiteSetting.
"""

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework.permissions import IsAuthenticated

from apps.core.models import AuditLog, SiteSetting
from apps.notifications.models import Notification
from apps.notifications.services import notify_event
from apps.referrals.models import Referral, ReferralCommission
from apps.support import services as support_services
from apps.support.models import SupportConversation
from apps.wallet.pagination import EnvelopePagination

from .permissions import GroupPermission
from .serializers import (
    AdminAuditLogSerializer,
    AdminCommissionSerializer,
    AdminNotificationSerializer,
    AdminReferralSerializer,
    AdminSiteSettingSerializer,
    AdminSupportConversationDetailSerializer,
    AdminSupportConversationListSerializer,
    AdminSupportReplySerializer,
    AdminSupportStatusSerializer,
)
from .views import AdminAPIView, envelope, error_envelope

User = get_user_model()


def _audit(actor, action: str, target_type: str, target_id: str, description: str, request=None) -> None:
    AuditLog.objects.create(
        actor_user=actor,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        description=description,
        ip_address=request.META.get('REMOTE_ADDR') if request else None,
        user_agent=(request.META.get('HTTP_USER_AGENT', '') or '')[:512] if request else '',
    )


# --------------------------------------------------------------------------- #
# Referrals & commissions (§40–43) — read-only
# --------------------------------------------------------------------------- #
class AdminReferralListView(AdminAPIView):
    def get(self, request):
        qs = Referral.objects.select_related('referrer', 'referred_user').order_by('-created_at')
        status_filter = (request.query_params.get('status') or '').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        referrer = (request.query_params.get('referrer') or '').strip()
        if referrer:
            qs = qs.filter(referrer__user_id__iexact=referrer)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AdminReferralSerializer(page, many=True).data)


class AdminCommissionListView(AdminAPIView):
    def get(self, request):
        qs = ReferralCommission.objects.select_related('user', 'source_user').order_by('-created_at')
        status_filter = (request.query_params.get('status') or '').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        level = (request.query_params.get('level') or '').strip()
        if level.isdigit():
            qs = qs.filter(level=int(level))
        beneficiary = (request.query_params.get('user') or '').strip()
        if beneficiary:
            qs = qs.filter(user__user_id__iexact=beneficiary)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AdminCommissionSerializer(page, many=True).data)


# --------------------------------------------------------------------------- #
# Support management (§44–48)
# --------------------------------------------------------------------------- #
class AdminSupportListCreateView(AdminAPIView):
    required_groups = ('Support Agents',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def get(self, request):
        qs = SupportConversation.objects.select_related('user').prefetch_related('messages').order_by('-updated_at')
        status_filter = (request.query_params.get('status') or '').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        search = (request.query_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(conversation_id__iexact=search)
                | Q(user__user_id__iexact=search)
                | Q(subject__icontains=search)
            )
        assigned = (request.query_params.get('assigned') or '').strip().lower()
        if assigned == 'me':
            qs = qs.filter(status__in=[
                SupportConversation.Status.OPEN, SupportConversation.Status.IN_PROGRESS,
            ])
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(
            AdminSupportConversationListSerializer(page, many=True).data
        )


class AdminSupportDetailView(AdminAPIView):
    required_groups = ('Support Agents',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def get(self, request, conversation_id: str):
        conversation = (
            SupportConversation.objects.select_related('user')
            .filter(conversation_id=conversation_id).first()
        )
        if conversation is None:
            return error_envelope('Conversation not found.', http_status=404)
        return envelope(AdminSupportConversationDetailSerializer(conversation).data)


class AdminSupportReplyView(AdminAPIView):
    """POST /api/admin/support/conversations/<conversation_id>/messages/ (§47)."""

    required_groups = ('Support Agents',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def post(self, request, conversation_id: str):
        conversation = (
            SupportConversation.objects.filter(conversation_id=conversation_id).first()
        )
        if conversation is None:
            return error_envelope('Conversation not found.', http_status=404)
        serializer = AdminSupportReplySerializer(data=request.data)
        if not serializer.is_valid():
            return error_envelope('Please correct the highlighted fields.', serializer.errors)
        try:
            support_services.send_message(
                request.user, conversation, serializer.validated_data['message'],
            )
        except support_services.SupportError as exc:
            return error_envelope(exc.message, exc.errors, http_status=exc.http_status)
        conversation.refresh_from_db()
        return envelope(
            AdminSupportConversationDetailSerializer(conversation).data,
            message='Reply sent.',
            http_status=201,
        )


class AdminSupportStatusView(AdminAPIView):
    """POST /api/admin/support/conversations/<conversation_id>/status/ (§48)."""

    required_groups = ('Support Agents',)
    permission_classes = [IsAuthenticated, GroupPermission]

    VALID = {
        SupportConversation.Status.OPEN,
        SupportConversation.Status.IN_PROGRESS,
        SupportConversation.Status.RESOLVED,
        SupportConversation.Status.CLOSED,
    }

    def post(self, request, conversation_id: str):
        conversation = (
            SupportConversation.objects.filter(conversation_id=conversation_id).first()
        )
        if conversation is None:
            return error_envelope('Conversation not found.', http_status=404)
        serializer = AdminSupportStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return error_envelope('Please correct the highlighted fields.', serializer.errors)
        new_status = serializer.validated_data['status']
        if new_status not in self.VALID:
            return error_envelope('Invalid status.', http_status=400)
        from django.utils import timezone

        old_status = conversation.status
        if old_status == new_status:
            return envelope(
                AdminSupportConversationDetailSerializer(conversation).data,
                message='Conversation already has that status.',
            )
        conversation.status = new_status
        if new_status == SupportConversation.Status.CLOSED:
            conversation.closed_at = timezone.now()
        elif old_status == SupportConversation.Status.CLOSED:
            conversation.closed_at = None
        conversation.save(update_fields=['status', 'closed_at', 'updated_at'])
        _audit(request.user, AuditLog.Action.UPDATE, 'admin.support_status',
               conversation.conversation_id, f'Status {old_status} → {new_status}', request)
        # §14: owner is told when staff changes their conversation status.
        notify_event(
            user=conversation.user,
            notification_type=Notification.NotificationType.SUPPORT,
            title='Support Conversation Updated',
            message=(
                f'Your support conversation "{conversation.subject}" status changed '
                f'from {old_status} to {new_status}.'
            ),
            event_key=(
                f'support:{conversation.conversation_id}:status:'
                f'{new_status.lower()}:{int(timezone.now().timestamp())}'
            ),
            related_type='support_conversation',
            related_id=conversation.conversation_id,
        )
        return envelope(
            AdminSupportConversationDetailSerializer(conversation).data,
            message='Status updated.',
        )


# --------------------------------------------------------------------------- #
# Notifications (§52–53)
# --------------------------------------------------------------------------- #
class AdminNotificationListView(AdminAPIView):
    def get(self, request):
        qs = Notification.objects.select_related('user').order_by('-created_at')
        type_filter = (request.query_params.get('type') or '').strip().upper()
        if type_filter:
            qs = qs.filter(notification_type=type_filter)
        user_filter = (request.query_params.get('user') or '').strip()
        if user_filter:
            qs = qs.filter(user__user_id__iexact=user_filter)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AdminNotificationSerializer(page, many=True).data)


class AdminBroadcastView(AdminAPIView):
    """POST /api/admin/notifications/broadcast/ (§52–53).

    Body: {title, message, audience}. Audience ∈ all_active | vip |
    with_deposits | with_withdrawals | with_referrals | user:<USER_ID>.
    Membership is ALWAYS computed server-side (§53). Plain text only.
    """

    required_groups = ('Notification Managers',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def post(self, request):
        payload = request.data or {}
        title = (payload.get('title') or '').strip()
        message = (payload.get('message') or '').strip()
        audience = (payload.get('audience') or 'all_active').strip()
        if not title or not message:
            return error_envelope(
                'Title and message are required.',
                {'title': ['Required.'] if not title else [], 'message': ['Required.'] if not message else []},
            )
        if len(title) > 200 or len(message) > 2000:
            return error_envelope('Title must be ≤200 and message ≤2000 characters.')

        users = User.objects.filter(account_status=User.AccountStatus.ACTIVE, is_active=True)
        if audience == 'all_active':
            pass  # default queryset above (§53: membership computed server-side)
        elif audience == 'vip':
            from apps.vip.models import VIPPurchase

            users = User.objects.filter(
                vip_purchases__status='ACTIVE',
                account_status=User.AccountStatus.ACTIVE,
            ).distinct()
        elif audience == 'with_deposits':
            from apps.deposits.models import Deposit

            users = User.objects.filter(
                deposits__isnull=False, account_status=User.AccountStatus.ACTIVE,
            ).distinct()
        elif audience == 'with_withdrawals':
            from apps.withdrawals.models import Withdrawal

            users = User.objects.filter(
                withdrawals__isnull=False, account_status=User.AccountStatus.ACTIVE,
            ).distinct()
        elif audience == 'with_referrals':
            users = User.objects.filter(
                referrals_made__isnull=False, account_status=User.AccountStatus.ACTIVE,
            ).distinct()
        elif audience.startswith('user:'):
            target_id = audience.split(':', 1)[1].strip()
            target = User.objects.filter(user_id=target_id).first()
            if target is None:
                return error_envelope('Target user not found.', http_status=404)
            users = User.objects.filter(pk=target.pk)
        else:
            return error_envelope('Unknown audience.', http_status=400)

        created = 0
        for user in users.iterator():
            Notification.objects.create(
                user=user,
                notification_type=Notification.NotificationType.SYSTEM,
                title=title,
                message=message,
            )
            created += 1
        _audit(request.user, AuditLog.Action.CREATE, 'admin.broadcast', audience,
               f'Broadcast "{title}" to {created} user(s)', request)
        return envelope({'delivered': created}, message='Broadcast sent.')


# --------------------------------------------------------------------------- #
# Audit logs (§54–55) — strictly read-only.
# --------------------------------------------------------------------------- #
class AdminAuditLogListView(AdminAPIView):
    def get(self, request):
        qs = AuditLog.objects.select_related('actor_user').order_by('-created_at')
        params = request.query_params
        action = (params.get('action') or '').strip().upper()
        if action:
            qs = qs.filter(action=action)
        actor = (params.get('actor') or '').strip()
        if actor:
            if actor.lower() == 'admin':
                qs = qs.filter(actor_user__is_staff=True)
            elif actor.lower() == 'user':
                qs = qs.filter(actor_user__is_staff=False)
            else:
                qs = qs.filter(actor_user__user_id__iexact=actor)
        target_type = (params.get('target_type') or '').strip()
        if target_type:
            qs = qs.filter(target_type__icontains=target_type)
        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AdminAuditLogSerializer(page, many=True).data)


# --------------------------------------------------------------------------- #
# Settings (§56–63)
# --------------------------------------------------------------------------- #
class AdminSettingsListEditView(AdminAPIView):
    """GET/PATCH /api/admin/settings/[?group=] (§56–63).

    PATCH body: {key, value, reason?} — one key per request, every change
    audited with old → new values. Config caches are invalidated so the
    withdrawal/referral engines pick up changes immediately.
    """

    required_groups = ('Settings Managers',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def get(self, request):
        group = (request.query_params.get('group') or '').strip().lower()
        qs = SiteSetting.objects.all().order_by('key')
        if group and group != 'all':
            qs = qs.filter(key__istartswith=group)
        return envelope({'results': AdminSiteSettingSerializer(qs, many=True).data})

    def patch(self, request):
        serializer = AdminSiteSettingSerializer(data=request.data)
        if not serializer.is_valid():
            return error_envelope('Please correct the highlighted fields.', serializer.errors)
        key = (request.data or {}).get('key')
        setting = SiteSetting.objects.filter(key=key).first()
        if setting is None:
            return error_envelope('Setting not found.', http_status=404)
        old_value = setting.value
        new_value = serializer.validated_data['value']
        if old_value == new_value:
            return envelope(AdminSiteSettingSerializer(setting).data, message='Setting unchanged.')
        setting.value = new_value
        setting.save(update_fields=['value', 'updated_at'])
        self._invalidate_caches(key)
        _audit(request.user, AuditLog.Action.UPDATE, 'admin.setting', key,
               f'Setting changed: {old_value!r} → {new_value!r}', request)
        return envelope(AdminSiteSettingSerializer(setting).data, message='Setting updated.')

    @staticmethod
    def _invalidate_caches(key: str) -> None:
        if key.startswith('withdrawal.'):
            from apps.withdrawals import config as wd_config

            wd_config.invalidate_cache()
        elif key.startswith('referral.'):
            from apps.referrals import config as ref_config

            ref_config.reset_cache()
