"""User-facing deposit API views (read + submit only; no status changes)."""

from decimal import Decimal

from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler
from apps.deposits.services import (
    DepositError,
    get_active_address,
    get_minimum_deposit,
    list_active_networks,
    qr_code_data_uri,
    submit_deposit,
)
from apps.wallet.models import Network

from .models import Deposit
from .serializers import (
    DepositAddressSerializer,
    DepositSerializer,
    NetworkSerializer,
    SubmitDepositSerializer,
)


def _exception_context(view) -> dict:
    return {'view': view, 'request': getattr(view, 'request', None), 'args': (), 'kwargs': {}}


class NetworkListView(APIView):
    """GET /api/deposits/networks/ — active networks for the deposit page."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        networks = list_active_networks()
        data = NetworkSerializer(
            [{'code': n.code, 'name': n.name, 'asset': n.asset} for n in networks], many=True,
        ).data
        return Response({'success': True, 'message': 'OK', 'data': data})

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class DepositRulesView(APIView):
    """GET /api/deposits/rules/ — configured minimum (Section 15 §9).

    The value is read through the same service the submit path validates
    with, so the UI can never display a different minimum than the backend
    enforces.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        minimum = get_minimum_deposit().quantize(Decimal('0.01'))
        return Response(
            {
                'success': True,
                'message': 'OK',
                'data': {'minimum_amount': str(minimum), 'asset': 'USDT'},
            }
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class DepositAddressView(APIView):
    """GET /api/deposits/address/?network=TRX — active address + QR.

    The QR is rendered server-side from the exact address returned, so it
    always matches what the user sees. Inactive/unknown networks 404.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        code = (request.query_params.get('network') or '').strip().upper()
        network = Network.objects.filter(code=code, is_active=True).first()
        if network is None:
            return Response(
                {'success': False, 'message': 'Network not found or unavailable.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        address = get_active_address(network)
        if address is None:
            return Response(
                {'success': False, 'message': 'No deposit address available for this network.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = DepositAddressSerializer(
            {
                'network': network.code,
                'asset': network.asset,
                'address': address.address,
                'qr_code': qr_code_data_uri(address),
            }
        ).data
        return Response({'success': True, 'message': 'OK', 'data': data})

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class SubmitThrottle(ScopedRateThrottle):
    """Throttle scope for financial submissions (Section 14 §30).

    Separate scope from the global user throttle so legitimate browsing is
    never blocked by a burst of submissions — and vice versa.
    """

    scope = 'fin_write'


class DepositCollectionView(APIView):
    """/api/deposits/ collection endpoint.

    GET  — the authenticated user's deposit history.
    POST — submit a new PENDING deposit (no wallet effect).
    """

    permission_classes = [IsAuthenticated]
    throttle_classes = [SubmitThrottle]

    def get(self, request):
        rows = Deposit.objects.filter(user=request.user)
        data = DepositSerializer(rows, many=True).data
        return Response({'success': True, 'message': 'OK', 'data': data})

    def post(self, request):
        serializer = SubmitDepositSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            result = submit_deposit(
                user=request.user,
                network_code=data['network'],
                amount=data['amount'],
                tx_hash=data.get('tx_hash', ''),
                order_id=data.get('order_id', ''),
            )
        except DepositError as exc:
            return Response(
                {'success': False, 'message': exc.message, 'errors': exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        body = DepositSerializer(result.deposit).data
        return Response(
            {'success': True, 'message': 'Deposit submitted and awaiting review.', 'data': body},
            status=status.HTTP_201_CREATED,
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class DepositDetailView(RetrieveAPIView):
    """GET /api/deposits/<deposit_id>/ — own deposit detail (others 404)."""

    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'deposit_id'
    lookup_url_kwarg = 'deposit_id'

    def get_queryset(self):
        return Deposit.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response({'success': True, 'message': 'OK', 'data': self.get_serializer(instance).data})

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


__all__ = [
    'DepositAddressView',
    'DepositCollectionView',
    'DepositDetailView',
    'DepositRulesView',
    'NetworkListView',
]
