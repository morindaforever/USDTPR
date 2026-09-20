"""VIP API views.

Business logic lives in services.py. ``/vip/current/`` (Section 4) remains;
the Section 7 endpoints add plan browsing, purchase, and history.
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler
from apps.wallet.pagination import EnvelopePagination
from apps.wallet.services import get_wallet_summary

from .models import VIPPlan, VIPPurchase, VIPReward
from .reward_service import active_purchases_with_progress
from .serializers import (
    CurrentPlanSerializer,
    VIPPlanSerializer,
    VIPPurchaseProgressSerializer,
    VIPPurchaseSerializer,
    VIPRewardSerializer,
)
from .services import VIPError, plan_purchase_summary, purchase_plan


def _exception_context(view) -> dict:
    return {'view': view, 'request': getattr(view, 'request', None), 'args': (), 'kwargs': {}}


class PlanListView(APIView):
    """GET /api/vip/plans/ — active plans.

    Public browsing is allowed per Section 7 §45 (recommended public plan
    list); account-specific data is never included here.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        plans = VIPPlan.objects.filter(is_active=True).order_by('sort_order', 'plan_number')
        data = VIPPlanSerializer(plans, many=True).data
        return Response({'success': True, 'message': 'OK', 'data': data})

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


class PlanDetailView(APIView):
    """GET /api/vip/plans/<id>/ — one active plan's details."""

    permission_classes = [AllowAny]

    def get(self, request, plan_id: int):
        plan = VIPPlan.objects.filter(pk=plan_id, is_active=True).first()
        if plan is None:
            return Response(
                {'success': False, 'message': 'Plan not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'success': True, 'message': 'OK', 'data': VIPPlanSerializer(plan).data})

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


class PlanSummaryView(APIView):
    """GET /api/vip/plans/<id>/summary/ — authoritative data for the
    purchase-confirmation modal: available balance and balance after the
    purchase, computed server-side. Never trust frontend numbers.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, plan_id: int):
        plan = VIPPlan.objects.filter(pk=plan_id, is_active=True).first()
        if plan is None:
            return Response(
                {'success': False, 'message': 'Plan not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        summary = plan_purchase_summary(request.user, plan)
        return Response(
            {
                'success': True,
                'message': 'OK',
                'data': {
                    'plan': VIPPlanSerializer(plan).data,
                    'available_balance': str(summary['available_balance']),
                    'balance_after_purchase': str(summary['balance_after_purchase']),
                    'sufficient': summary['sufficient'],
                },
            }
        )

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


class ActivePlansView(APIView):
    """GET /api/vip/active/ — the user's active/completed purchases with
    backend-computed reward progress (Section 8 §22).

    ``rewarded_amount``/``remaining_amount``/``progress_percent`` are derived
    from persisted VIPReward rows in one aggregated query — the frontend
    never calculates authoritative progress (§64).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = active_purchases_with_progress(request.user)
        data = VIPPurchaseProgressSerializer(rows, many=True).data
        return Response({'success': True, 'message': 'OK', 'data': data})

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


class RewardListView(APIView):
    """GET /api/vip/rewards/ — the user's own reward history (§20).

    Paginated with the platform envelope. Optional ``purchase_id`` filter
    scopes to one purchase. Cross-user access is structurally impossible:
    the queryset is always scoped by ``request.user`` (§21, §57).
    """

    permission_classes = [IsAuthenticated]
    pagination_class = EnvelopePagination

    def get(self, request):
        rows = VIPReward.objects.filter(user=request.user).select_related(
            'vip_purchase', 'wallet_transaction',
        )
        purchase_ref = request.query_params.get('purchase_id')
        if purchase_ref:
            rows = rows.filter(vip_purchase__purchase_id=purchase_ref)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(rows, request, view=self)
        data = VIPRewardSerializer(page, many=True).data
        return paginator.get_paginated_response(data)

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


class RewardDetailView(APIView):
    """GET /api/vip/rewards/<reward_id>/ — the owner's reward detail (§21).

    Public-ID lookup scoped to ``request.user``: another user's reward (or
    an invalid ID) 404s without leaking existence — the platform's IDOR
    convention (§61).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, reward_id: str):
        reward = (
            VIPReward.objects.filter(user=request.user, reward_id=reward_id)
            .select_related('vip_purchase', 'wallet_transaction')
            .first()
        )
        if reward is None:
            return Response(
                {'success': False, 'message': 'Reward not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({'success': True, 'message': 'OK', 'data': VIPRewardSerializer(reward).data})

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


class PurchaseHistoryView(APIView):
    """GET /api/vip/purchases/ — the user's purchases, newest first."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = VIPPurchase.objects.filter(user=request.user)
        data = VIPPurchaseSerializer(rows, many=True).data
        return Response({'success': True, 'message': 'OK', 'data': data})

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


class PurchaseView(APIView):
    """POST /api/vip/purchase/ — buy a plan with withdrawable balance.

    Body: {"plan_id": 3, "idempotency_key": "client-generated-unique"}
    All financial values are loaded server-side from the plan row.
    """

    permission_classes = [IsAuthenticated]
    # Financial submission throttle (Section 14 §30).
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'fin_write'

    def post(self, request):
        plan_id = (request.data or {}).get('plan_id')
        idempotency_key = (request.data or {}).get('idempotency_key') or ''
        try:
            result = purchase_plan(user=request.user, plan_id=plan_id, idempotency_key=idempotency_key)
        except VIPError as exc:
            return Response(
                {'success': False, 'message': exc.message, 'errors': exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Combined spendable remaining (deposit + withdrawable) — matches
        # what the next purchase could actually spend.
        summary = get_wallet_summary(request.user)
        remaining = (summary['deposit_balance'] + summary['withdrawable_balance']).quantize(
            Decimal('0.00000001')
        )
        message = (
            'Purchase already completed previously.'
            if result.already_existed
            else 'VIP plan activated successfully.'
        )
        return Response(
            {
                'success': True,
                'message': message,
                'data': {
                    'purchase': VIPPurchaseSerializer(result.purchase).data,
                    'remaining_balance': str(remaining),
                    'already_existed': result.already_existed,
                },
            },
            status=status.HTTP_200_OK if result.already_existed else status.HTTP_201_CREATED,
        )

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


class CurrentPlanView(APIView):
    """GET /api/vip/current/ — the user's active purchase (Section 4).

    Returns ``data: null`` when there is no active plan (the frontend shows
    the empty state). Zero-investment welcome-plan purchases surface here
    with ``is_welcome_plan: true`` so the UI can label them as the free plan.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        purchase = (
            VIPPurchase.objects.filter(user=request.user, status=VIPPurchase.Status.ACTIVE)
            .order_by('-started_at', '-created_at')
            .first()
        )
        data = CurrentPlanSerializer(purchase).data if purchase else None
        return Response({'success': True, 'message': 'OK', 'data': data})

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


__all__ = [
    'ActivePlansView',
    'CurrentPlanView',
    'PlanDetailView',
    'PlanListView',
    'PurchaseHistoryView',
    'PurchaseView',
]
