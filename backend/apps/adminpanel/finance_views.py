"""Admin financial management views (Section 12 §18–§39, §49–§51).

Everything delegates to the EXISTING Section 6/7/8/10 services — the admin
panel adds authorization + presentation, never new accounting logic. All
actions are idempotent and audited; no endpoint can edit a wallet balance
directly (§50).
"""

from decimal import Decimal, InvalidOperation

from django.db import transaction as db_transaction
from rest_framework.permissions import IsAuthenticated

from apps.core.models import AuditLog
from apps.deposits.admin_urls import ApproveView  # noqa: F401 (route reuse)
from apps.deposits.models import Deposit
from apps.deposits.services import approve_deposit, reject_deposit
from apps.deposits.services import DepositError
from apps.vip.models import VIPPlan, VIPPurchase, VIPReward
from apps.vip.reward_service import current_cycle, process_daily_rewards
from apps.wallet.models import WalletTransaction
from apps.wallet.pagination import EnvelopePagination
from apps.withdrawals.models import Withdrawal
from apps.withdrawals import services as withdrawal_services

from .permissions import GroupPermission
from .serializers import (
    AdminTransactionSerializer,
    AdminVIPPlanListSerializer,
    AdminVIPPlanSerializer,
    AdminVIPPurchaseSerializer,
    AdminVIPRewardSerializer,
)
from .views import AdminAPIView, envelope, error_envelope


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


def _flag(value: str) -> bool:
    return (value or '').strip().lower() in ('true', '1', 'yes')


def _decimal(value, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError) as exc:
        raise ValueError(f'{field} must be a decimal number.') from exc


# --------------------------------------------------------------------------- #
# Deposits (§18–21) — the list/detail live in the deposits app's admin module;
# this module re-exposes them under /api/admin/ for route consistency.
# --------------------------------------------------------------------------- #
class AdminDepositListView(AdminAPIView):
    def get(self, request):
        from apps.deposits.admin_views import AdminDepositListView as _List

        return _List.as_view()(request._request)


class AdminDepositDetailView(AdminAPIView):
    def get(self, request, deposit_id: str):
        from apps.deposits.admin_views import AdminDepositDetailView as _Detail

        return _Detail.as_view()(request._request, deposit_id=deposit_id)


class AdminDepositActionView(AdminAPIView):
    """POST /api/admin/deposits/<deposit_id>/approve|reject/ (§20–21)."""

    required_groups = ('Deposit Approvers',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def post(self, request, deposit_id: str, action: str):
        deposit = Deposit.objects.filter(deposit_id=deposit_id).first()
        if deposit is None:
            return error_envelope('Deposit not found.', http_status=404)
        note = ((request.data or {}).get('reason') or (request.data or {}).get('note') or '').strip()
        try:
            if action == 'approve':
                deposit = approve_deposit(deposit=deposit, admin_user=request.user, note=note)
                message = 'Deposit approved and credited.'
            elif action == 'reject':
                if not note:
                    return error_envelope('A rejection reason is required.', {'reason': ['Required.']})
                deposit = reject_deposit(deposit=deposit, admin_user=request.user, reason=note)
                message = 'Deposit rejected.'
            else:
                return error_envelope('Unknown action.', http_status=404)
        except DepositError as exc:
            return error_envelope(exc.message, exc.errors, http_status=400)
        return envelope({'deposit': __import__('apps.deposits.serializers', fromlist=['DepositSerializer']).DepositSerializer(deposit).data}, message=message)


# --------------------------------------------------------------------------- #
# Withdrawals (§24–29) — reuse the Section 10 state machine functions.
# --------------------------------------------------------------------------- #
class AdminWithdrawalListView(AdminAPIView):
    def get(self, request):
        from apps.withdrawals.views import AdminWithdrawalListView as _List

        return _List.as_view()(request._request)


class AdminWithdrawalDetailView(AdminAPIView):
    def get(self, request, withdrawal_id: str):
        from apps.withdrawals.views import AdminWithdrawalDetailView as _Detail

        return _Detail.as_view()(request._request, withdrawal_id=withdrawal_id)


class AdminWithdrawalActionView(AdminAPIView):
    """POST /api/admin/withdrawals/<withdrawal_id>/<action>/ (§26–29).

    Approve/processing require the Withdrawal Approvers group;
    complete/fail require Withdrawal Completers. Reject requires a reason.
    """

    permission_classes = [IsAuthenticated, GroupPermission]
    required_groups = ('Withdrawal Approvers',)

    def post(self, request, withdrawal_id: str, action: str):
        if action in ('complete', 'fail'):
            if not (request.user.is_superuser
                    or request.user.groups.filter(name='Withdrawal Completers').exists()):
                return error_envelope('You do not have permission to perform this action.', http_status=403)
        payload = request.data or {}
        reason = (payload.get('reason') or '').strip()
        tx_hash = (payload.get('transaction_hash') or '').strip()
        try:
            if action == 'approve':
                w = withdrawal_services.approve_withdrawal(withdrawal_id, admin=request.user, admin_note=reason)
                message = 'Withdrawal approved; funds remain locked.'
            elif action == 'reject':
                if not reason:
                    return error_envelope('A rejection reason is required.', {'reason': ['Required.']})
                w = withdrawal_services.reject_withdrawal(withdrawal_id, admin=request.user, reason=reason)
                message = 'Withdrawal rejected; locked funds released.'
            elif action == 'processing':
                w = withdrawal_services.start_processing(withdrawal_id, admin=request.user, admin_note=reason)
                message = 'Withdrawal moved to processing.'
            elif action == 'complete':
                w = withdrawal_services.complete_withdrawal(
                    withdrawal_id, admin=request.user, tx_hash=tx_hash, admin_note=reason,
                )
                message = 'Withdrawal completed.'
            elif action == 'fail':
                w = withdrawal_services.fail_withdrawal(withdrawal_id, admin=request.user, reason=reason)
                message = 'Withdrawal failed; locked funds released.'
            else:
                return error_envelope('Unknown action.', http_status=404)
        except withdrawal_services.InvalidTransitionError as exc:
            return error_envelope(str(exc), http_status=409)
        except withdrawal_services.WithdrawalError as exc:
            return error_envelope(exc.message, exc.errors, http_status=400)
        from apps.withdrawals.serializers import WithdrawalAdminSerializer

        return envelope({'withdrawal': WithdrawalAdminSerializer(w).data}, message=message)


# --------------------------------------------------------------------------- #
# VIP plans (§30–33)
# --------------------------------------------------------------------------- #
class AdminVIPPlanListCreateView(AdminAPIView):
    required_groups = ('VIP Managers',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def get(self, request):
        plans = VIPPlan.objects.order_by('sort_order', 'plan_number')
        return envelope({'results': AdminVIPPlanListSerializer(plans, many=True).data})

    def post(self, request):
        serializer = AdminVIPPlanSerializer(data=request.data)
        if not serializer.is_valid():
            return error_envelope('Please correct the highlighted fields.', serializer.errors)
        plan = serializer.save()
        _audit(request.user, AuditLog.Action.CREATE, 'admin.vip_plan', plan.name,
               f'VIP plan created: {plan.name} (investment {plan.investment_amount}, '
               f'target {plan.target_amount}, rate {plan.daily_rate})', request)
        return envelope(AdminVIPPlanListSerializer(plan).data, message='VIP plan created.', http_status=201)


class AdminVIPPlanDetailView(AdminAPIView):
    required_groups = ('VIP Managers',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def get(self, request, pk: int):
        plan = VIPPlan.objects.filter(pk=pk).first()
        if plan is None:
            return error_envelope('VIP plan not found.', http_status=404)
        return envelope(AdminVIPPlanListSerializer(plan).data)

    def patch(self, request, pk: int):
        plan = VIPPlan.objects.filter(pk=pk).first()
        if plan is None:
            return error_envelope('VIP plan not found.', http_status=404)
        serializer = AdminVIPPlanSerializer(plan, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_envelope('Please correct the highlighted fields.', serializer.errors)
        old = (str(plan.investment_amount), str(plan.target_amount), str(plan.daily_rate), plan.is_active)
        updated = serializer.save()
        new = (str(updated.investment_amount), str(updated.target_amount), str(updated.daily_rate), updated.is_active)
        _audit(request.user, AuditLog.Action.UPDATE, 'admin.vip_plan', updated.name,
               f'VIP plan updated: {old} → {new}. Existing purchase snapshots are unchanged.', request)
        return envelope(AdminVIPPlanListSerializer(updated).data, message='VIP plan updated.')


class AdminVIPPurchaseListView(AdminAPIView):
    def get(self, request):
        qs = VIPPurchase.objects.select_related('user').order_by('-created_at')
        status_filter = (request.query_params.get('status') or '').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        user_filter = (request.query_params.get('user') or '').strip()
        if user_filter:
            qs = qs.filter(user__user_id__iexact=user_filter)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AdminVIPPurchaseSerializer(page, many=True).data)


# --------------------------------------------------------------------------- #
# Rewards (§36–39) — trigger/retry through the EXISTING service.
# --------------------------------------------------------------------------- #
class AdminRewardListView(AdminAPIView):
    def get(self, request):
        qs = VIPReward.objects.select_related('user', 'vip_purchase').order_by('-created_at')
        status_filter = (request.query_params.get('status') or '').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        user_filter = (request.query_params.get('user') or '').strip()
        if user_filter:
            qs = qs.filter(user__user_id__iexact=user_filter)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AdminVIPRewardSerializer(page, many=True).data)


class AdminRewardProcessView(AdminAPIView):
    """POST /api/admin/rewards/process/  body: {cycle_date?} (§38).

    Calls the SAME ``process_daily_rewards`` used by Celery Beat — no
    duplicate calculation logic. Idempotent per (purchase, cycle).
    """

    required_groups = ('Reward Processors',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def post(self, request):
        cycle_raw = ((request.data or {}).get('cycle_date') or '').strip()
        cycle = None
        if cycle_raw:
            from datetime import date

            try:
                cycle = date.fromisoformat(cycle_raw)
            except ValueError as exc:
                return error_envelope('cycle_date must be an ISO date (YYYY-MM-DD).', http_status=400)
        stats = process_daily_rewards(cycle_date=cycle)
        _audit(request.user, AuditLog.Action.OTHER, 'admin.reward_process',
               (cycle or current_cycle()).isoformat(),
               f'Manual reward processing: {stats}', request)
        return envelope({'result': stats}, message='Reward processing finished.')


class AdminRewardRetryView(AdminAPIView):
    """POST /api/admin/rewards/<reward_id>/retry/ (§39).

    Re-runs the idempotent engine for the reward's purchase+cycle; credited
    rewards skip, failed/pending rows reclaim and re-credit at most once.
    """

    required_groups = ('Reward Processors',)
    permission_classes = [IsAuthenticated, GroupPermission]

    def post(self, request, reward_id: str):
        reward = (
            VIPReward.objects.select_related('vip_purchase').filter(reward_id=reward_id).first()
        )
        if reward is None:
            return error_envelope('Reward not found.', http_status=404)
        if reward.status == 'COMPLETED':
            return envelope(
                AdminVIPRewardSerializer(reward).data,
                message='Reward already completed; nothing to retry.',
            )
        from apps.vip.reward_service import process_reward

        try:
            outcome = process_reward(reward.vip_purchase_id, cycle_date=reward.reward_date)
        except Exception as exc:  # engine raises on wallet failure etc.
            return error_envelope(f'Retry failed: {exc}', http_status=409)
        reward.refresh_from_db()
        _audit(request.user, AuditLog.Action.OTHER, 'admin.reward_retry', reward.reward_id,
               f'Reward retry outcome: {outcome}', request)
        return envelope(AdminVIPRewardSerializer(reward).data, message='Reward retry finished.')


# --------------------------------------------------------------------------- #
# Wallet transactions (§49–50) — strictly read-only ledger viewer.
# --------------------------------------------------------------------------- #
class AdminTransactionListView(AdminAPIView):
    def get(self, request):
        qs = WalletTransaction.objects.select_related('user').order_by('-created_at')
        params = request.query_params
        type_filter = (params.get('type') or '').strip().upper()
        if type_filter:
            qs = qs.filter(transaction_type=type_filter)
        direction = (params.get('direction') or '').strip().upper()
        if direction:
            qs = qs.filter(direction=direction)
        user_filter = (params.get('user') or '').strip()
        if user_filter:
            qs = qs.filter(user__user_id__iexact=user_filter)
        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(AdminTransactionSerializer(page, many=True).data)
