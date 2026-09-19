"""Wallet API views.

Section 5 scope: READ-ONLY endpoints. Balance mutations are internal service
functions (apps.wallet.services) used by backend modules — there is
deliberately no POST /credit, /debit, or /adjust API for users.
"""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler
from apps.wallet.services import WalletError, WalletNotFoundError, get_wallet

from .models import WalletTransaction
from .pagination import EnvelopePagination
from .serializers import WalletSummarySerializer, WalletTransactionSerializer


def _exception_context(view) -> dict:
    """Context shim for api_exception_handler (it only reads view)."""
    return {'view': view, 'request': getattr(view, 'request', None), 'args': (), 'kwargs': {}}


class WalletSummaryView(APIView):
    """GET /api/wallet/summary/ — the authenticated user's wallet only.

    The user is always taken from the authenticated request; there is no
    ``user_id`` parameter by design, so one user can never read another's
    balances.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            wallet = get_wallet(request.user)
        except WalletNotFoundError:
            return Response(
                {'success': False, 'message': 'Wallet not found for this account.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        data = WalletSummarySerializer(wallet).data
        return Response({'success': True, 'message': 'OK', 'data': data})

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class TransactionListView(ListAPIView):
    """GET /api/wallet/transactions/ — paginated ledger history (own rows).

    Filters: ``type``, ``status``, ``direction``, ``date_from``, ``date_to``
    (inclusive, ISO dates). Every filter applies inside the authenticated
    user's dataset — cross-user access is structurally impossible because
    the queryset is scoped by ``request.user``.
    """

    serializer_class = WalletTransactionSerializer
    pagination_class = EnvelopePagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = WalletTransaction.objects.filter(user=self.request.user).order_by('-created_at', '-id')
        params = self.request.query_params
        txn_type = params.get('type')
        if txn_type:
            qs = qs.filter(transaction_type=txn_type.upper())
        txn_status = params.get('status')
        if txn_status:
            qs = qs.filter(status=txn_status.upper())
        direction = params.get('direction')
        if direction:
            qs = qs.filter(direction=direction.upper())
        # §23: search over safe indexed fields only (id, description, ref).
        search = (params.get('search') or '').strip()
        if search:
            if search.upper().startswith('TXN'):
                qs = qs.filter(transaction_id__iexact=search)
            else:
                qs = qs.filter(
                    Q(description__icontains=search)
                    | Q(reference_id__iexact=search)
                    | Q(transaction_id__iexact=search)
                )
        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    def list(self, request, *args, **kwargs):
        # Malformed filter dates etc. become a clean 400 rather than a 500.
        try:
            return super().list(request, *args, **kwargs)
        except (ValueError, DjangoValidationError):
            return Response(
                {'success': False, 'message': 'Invalid filter value.', 'errors': {}},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def handle_exception(self, exc):
        if isinstance(exc, WalletError):
            return Response(
                {'success': False, 'message': exc.message, 'errors': {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return api_exception_handler(exc, _exception_context(self))


class TransactionDetailView(RetrieveAPIView):
    """GET /api/wallet/transactions/<transaction_id>/ — own row only.

    Lookups use the public ``transaction_id`` (TXN…) scoped to the
    authenticated user, so other users' transactions 404 (no existence
    leak) instead of 403.
    """

    serializer_class = WalletTransactionSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'transaction_id'
    lookup_url_kwarg = 'transaction_id'

    def get_queryset(self):
        return WalletTransaction.objects.filter(user=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        data = self.get_serializer(instance).data
        return Response({'success': True, 'message': 'OK', 'data': data})

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


__all__ = ['TransactionDetailView', 'TransactionListView', 'WalletSummaryView']
