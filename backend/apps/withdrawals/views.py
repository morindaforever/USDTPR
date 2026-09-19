"""Withdrawal app API views.

Section 4 contributed the activity feed only; Section 10 adds the real
withdrawal system around it. User endpoints are authenticated and
owner-scoped (§39, §69); admin endpoints additionally require ``is_staff``
(§48, §54). Domain errors use the standard ``{success, message, errors}``
envelope — stack traces never surface (§61).

The frontend never supplies financial values (§63, §69): amounts/fees/net
are recomputed server-side by ``services``; the client only names the
network, address, amount, and an idempotency key.
"""

from decimal import Decimal

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler
from apps.deposits.admin_permissions import IsAdminUser
from apps.wallet.models import Network
from apps.wallet.pagination import EnvelopePagination
from apps.wallet.services import WalletError, get_wallet_summary

from . import config, services
from .address_validation import address_hint
from .models import Withdrawal
from .serializers import (
    WithdrawalAdminSerializer,
    WithdrawalCreateSerializer,
    WithdrawalDetailSerializer,
    WithdrawalListSerializer,
    WithdrawalQuoteSerializer,
)


def _exception_context(view) -> dict:
    """Context shim for api_exception_handler (it only reads ``view``)."""
    return {'view': view, 'request': getattr(view, 'request', None), 'args': (), 'kwargs': {}}


class _AuthedAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


def _domain_error(exc: services.WithdrawalError) -> Response:
    """Envelope for WithdrawalError-family domain errors (§61)."""
    return Response(
        {'success': False, 'message': exc.message, 'errors': exc.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _envelope(data, message: str = 'OK', http_status: int = status.HTTP_200_OK) -> Response:
    return Response({'success': True, 'message': message, 'data': data}, status=http_status)


# --------------------------------------------------------------------------- #
# Public configuration endpoints (§7, §46)
# --------------------------------------------------------------------------- #
class NetworkListView(_AuthedAPIView):
    """GET /api/withdrawals/networks/ — active networks with address hints.

    Everything comes from the Network table; the address ``hint`` is format
    guidance only (§10: "Format validation only" — never on-chain proof).
    """

    def get(self, request):
        rows = Network.objects.filter(is_active=True).order_by('sort_order', 'code')
        data = [
            {
                'code': n.code,
                'name': n.name,
                'asset': n.asset,
                'address_hint': address_hint(n.code),
            }
            for n in rows
        ]
        return _envelope(data)


class RulesView(_AuthedAPIView):
    """GET /api/withdrawals/rules/ — public withdrawal rules (§46).

    Only user-relevant values are exposed; internal SiteSetting keys and
    admin-only configuration stay behind the admin surface.
    """

    def get(self, request):
        minimum = config.get_min_amount()
        fee_type = config.get_fee_type()
        fee_amount = config.get_fee_amount()
        return _envelope({
            'minimum_amount': str(minimum.quantize(Decimal('0.01'))),
            'fee_type': fee_type,
            'fee_amount': str(fee_amount.quantize(Decimal('0.01'))),
            'fee_unit': 'USDT' if fee_type == 'FIXED' else 'PERCENT',
        })


# --------------------------------------------------------------------------- #
# User withdrawal endpoints (§18, §38–41, §47)
# --------------------------------------------------------------------------- #
class WithdrawalSummaryView(_AuthedAPIView):
    """GET /api/withdrawals/summary/ — balances for /withdraw (§41).

    ``withdrawable_balance``/``locked_balance`` come straight from the
    wallet service; ``pending_withdrawals`` is the persisted sum of the
    user's non-terminal withdrawals. Nothing is computed client-side.
    """

    def get(self, request):
        summary = get_wallet_summary(request.user)
        return _envelope({
            'withdrawable_balance': str(summary['withdrawable_balance'].quantize(Decimal('0.01'))),
            'locked_balance': str(summary['locked_balance'].quantize(Decimal('0.01'))),
            'pending_withdrawals': str(services.pending_withdrawal_total(request.user)),
        })


class QuoteView(_AuthedAPIView):
    """POST /api/withdrawals/quote/ — informational fee/net breakdown (§47).

    Submission always recalculates; a stale or tampered quote can never
    influence the actual withdrawal.
    """

    def post(self, request):
        serializer = WithdrawalQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        try:
            data = services.quote(v['amount'], v.get('network'))
        except services.WithdrawalError as exc:
            return _domain_error(exc)
        return _envelope(data)


class WithdrawalListCreateView(_AuthedAPIView):
    """GET /api/withdrawals/ (paginated, newest first) + POST to submit (§18).

    POST is throttled via the shared ``fin_write`` scope (Section 14 §30).
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'fin_write'

    def get(self, request):
        qs = (
            Withdrawal.objects.filter(user=request.user)
            .select_related('network')
            .order_by('-created_at')
        )
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(WithdrawalListSerializer(page, many=True).data)

    def post(self, request):
        serializer = WithdrawalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v = serializer.validated_data
        try:
            withdrawal, created = services.create_withdrawal(
                user=request.user,
                network_code=v['network'],
                destination_address=v['destination_address'],
                amount=v['amount'],
                idempotency_key=v['idempotency_key'],
            )
        except services.WithdrawalError as exc:
            return _domain_error(exc)
        except WalletError as exc:  # e.g. insufficient balance during lock (§37)
            return _domain_error(services.WithdrawalError(str(exc.message)))
        # Idempotent replay returns the ORIGINAL withdrawal with 200 (§35).
        return _envelope(
            WithdrawalDetailSerializer(withdrawal).data,
            message=(
                'Withdrawal request submitted.'
                if created
                else 'Withdrawal request already exists.'
            ),
            http_status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class WithdrawalDetailView(_AuthedAPIView):
    """GET /api/withdrawals/<withdrawal_id>/ — owner-only detail (§39, §44)."""

    def get(self, request, withdrawal_id: str):
        withdrawal = (
            Withdrawal.objects.select_related('network')
            .filter(withdrawal_id=withdrawal_id, user=request.user)
            .first()
        )
        if withdrawal is None:
            return Response(
                {'success': False, 'message': 'Withdrawal not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return _envelope(WithdrawalDetailSerializer(withdrawal).data)


# --------------------------------------------------------------------------- #
# Admin endpoints (§48–54) — mounted under /api/admin-panel/
# --------------------------------------------------------------------------- #
class _AdminAPIView(_AuthedAPIView):
    permission_classes = [IsAuthenticated, IsAdminUser]


class AdminWithdrawalListView(_AdminAPIView):
    """GET /api/admin-panel/withdrawals/?status= — paginated admin queue (§79)."""

    def get(self, request):
        qs = Withdrawal.objects.select_related('user', 'network').order_by('-created_at')
        status_filter = (request.query_params.get('status') or '').strip().upper()
        if status_filter:
            qs = qs.filter(status=status_filter)
        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(WithdrawalAdminSerializer(page, many=True).data)


class AdminWithdrawalDetailView(_AdminAPIView):
    """GET /api/admin-panel/withdrawals/<withdrawal_id>/ — full record."""

    def get(self, request, withdrawal_id: str):
        withdrawal = (
            Withdrawal.objects.select_related('user', 'network')
            .filter(withdrawal_id=withdrawal_id)
            .first()
        )
        if withdrawal is None:
            return Response(
                {'success': False, 'message': 'Withdrawal not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        return _envelope(WithdrawalAdminSerializer(withdrawal).data)


class AdminWithdrawalActionView(_AdminAPIView):
    """Shared handler for the five fixed admin transitions (§49–53).

    The client can only supply a note, a rejection/failure reason, and an
    optional transaction hash (stored verbatim — never generated, §32).
    Statuses and financial values are untouchable; transitions are enforced
    by the service's state machine.
    """

    def post(self, request, withdrawal_id: str, action: str):  # noqa: D102 - fixed per subclass
        body = request.data or {}
        admin_note = str(body.get('admin_note') or '')[:500]
        try:
            if action == 'approve':
                withdrawal = services.approve_withdrawal(withdrawal_id, admin=request.user, admin_note=admin_note)
            elif action == 'reject':
                reason = str(body.get('reason') or '').strip()
                if not reason:
                    return Response(
                        {
                            'success': False,
                            'message': 'A rejection reason is required.',
                            'errors': {'reason': ['This field is required.']},
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                withdrawal = services.reject_withdrawal(
                    withdrawal_id, admin=request.user, reason=reason, admin_note=admin_note,
                )
            elif action == 'processing':
                withdrawal = services.start_processing(withdrawal_id, admin=request.user, admin_note=admin_note)
            elif action == 'complete':
                withdrawal = services.complete_withdrawal(
                    withdrawal_id,
                    admin=request.user,
                    tx_hash=str(body.get('transaction_hash') or '').strip(),
                    admin_note=admin_note,
                )
            elif action == 'fail':
                withdrawal = services.fail_withdrawal(
                    withdrawal_id,
                    admin=request.user,
                    reason=str(body.get('reason') or '').strip(),
                    admin_note=admin_note,
                )
            else:
                return Response(
                    {'success': False, 'message': 'Unknown action.', 'errors': {}},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except services.InvalidTransitionError as exc:
            return Response(
                {'success': False, 'message': str(exc), 'errors': {}},
                status=status.HTTP_409_CONFLICT,
            )
        except services.WithdrawalError as exc:
            return _domain_error(exc)
        except WalletError as exc:  # release/finalize anomaly — never 500-leak
            return _domain_error(services.WithdrawalError(str(exc.message)))

        message_by_action = {
            'approve': 'Withdrawal approved.',
            'reject': 'Withdrawal rejected.',
            'processing': 'Withdrawal moved to processing.',
            'complete': 'Withdrawal completed.',
            'fail': 'Withdrawal marked as failed.',
        }
        return _envelope(WithdrawalAdminSerializer(withdrawal).data, message=message_by_action[action])


# Fixed-action subclasses (mirrors the deposits admin_urls pattern).
class AdminApproveView(AdminWithdrawalActionView):
    def post(self, request, withdrawal_id: str):  # noqa: D102 - action fixed
        return super().post(request, withdrawal_id, 'approve')


class AdminRejectView(AdminWithdrawalActionView):
    def post(self, request, withdrawal_id: str):  # noqa: D102 - action fixed
        return super().post(request, withdrawal_id, 'reject')


class AdminProcessingView(AdminWithdrawalActionView):
    def post(self, request, withdrawal_id: str):  # noqa: D102 - action fixed
        return super().post(request, withdrawal_id, 'processing')


class AdminCompleteView(AdminWithdrawalActionView):
    def post(self, request, withdrawal_id: str):  # noqa: D102 - action fixed
        return super().post(request, withdrawal_id, 'complete')


class AdminFailView(AdminWithdrawalActionView):
    def post(self, request, withdrawal_id: str):  # noqa: D102 - action fixed
        return super().post(request, withdrawal_id, 'fail')


__all__ = [
    'NetworkListView',
    'RulesView',
    'WithdrawalSummaryView',
    'QuoteView',
    'WithdrawalListCreateView',
    'WithdrawalDetailView',
    'AdminWithdrawalListView',
    'AdminWithdrawalDetailView',
    'AdminWithdrawalActionView',
    'AdminApproveView',
    'AdminRejectView',
    'AdminProcessingView',
    'AdminCompleteView',
    'AdminFailView',
]
