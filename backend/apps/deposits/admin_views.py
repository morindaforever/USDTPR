"""Admin deposit-management API views (is_staff required on every route)."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction as db_transaction
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler
from apps.wallet.models import DepositAddress, Network
from apps.wallet.pagination import EnvelopePagination

from .admin_permissions import IsAdminUser
from .models import Deposit
from .serializers import DepositSerializer
from .services import approve_deposit, get_active_address, reject_deposit


def _exception_context(view) -> dict:
    return {'view': view, 'request': getattr(view, 'request', None), 'args': (), 'kwargs': {}}


class AdminDepositListView(ListAPIView):
    """GET /api/admin/deposits/ — filterable, paginated deposit list.

    Filters: status, network (code), user (public user ID), deposit_id,
    tx_hash, date_from/date_to (inclusive). Paginated 20/page.
    """

    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = EnvelopePagination

    def get_queryset(self):
        qs = Deposit.objects.select_related('user', 'network').order_by('-created_at', '-id')
        params = self.request.query_params
        dep_status = params.get('status')
        if dep_status:
            qs = qs.filter(status=dep_status.upper())
        network = params.get('network')
        if network:
            qs = qs.filter(network__code=network.upper())
        user_id = params.get('user')
        if user_id:
            qs = qs.filter(user__user_id__iexact=user_id)
        deposit_id = params.get('deposit_id')
        if deposit_id:
            qs = qs.filter(deposit_id__iexact=deposit_id)
        tx_hash = params.get('tx_hash')
        if tx_hash:
            qs = qs.filter(tx_hash__iexact=tx_hash)
        date_from = params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)
        return qs

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except (ValueError, DjangoValidationError):
            return Response(
                {'success': False, 'message': 'Invalid filter value.', 'errors': {}},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class AdminDepositDetailView(RetrieveAPIView):
    """GET /api/admin/deposits/<deposit_id>/ — full admin detail view."""

    serializer_class = DepositSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    lookup_field = 'deposit_id'
    lookup_url_kwarg = 'deposit_id'
    queryset = Deposit.objects.select_related('user', 'network')

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        return Response({'success': True, 'message': 'OK', 'data': self.get_serializer(instance).data})

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class AdminDepositActionView(APIView):
    """POST /api/admin/deposits/<deposit_id>/approve|reject/

    The URL route captures the action name; kwargs['action'] selects the
    operation (approve or reject).
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request, deposit_id: str, action: str = ''):
        action = action or self.kwargs.get('action', '')
        deposit = Deposit.objects.filter(deposit_id=deposit_id).first()
        if deposit is None:
            return Response(
                {'success': False, 'message': 'Deposit not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        note_or_reason = (request.data or {}).get('reason') or (request.data or {}).get('note') or ''
        try:
            if action == 'approve':
                deposit = approve_deposit(
                    deposit=deposit, admin_user=request.user, note=note_or_reason,
                )
                message = 'Deposit approved and credited.'
            elif action == 'reject':
                deposit = reject_deposit(
                    deposit=deposit, admin_user=request.user, reason=note_or_reason,
                )
                message = 'Deposit rejected.'
            else:
                return Response(
                    {'success': False, 'message': 'Unknown action.', 'errors': {}},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except DepositError as exc:
            return Response(
                {'success': False, 'message': exc.message, 'errors': exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {
                'success': True,
                'message': message,
                'data': DepositSerializer(deposit).data,
            }
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class AdminDepositApproveView(AdminDepositActionView):
    def post(self, request, deposit_id: str):  # pragma: no cover - delegates
        return super().post(request, deposit_id, 'approve')


# --------------------------------------------------------------------------- #
# Deposit address & network management
# --------------------------------------------------------------------------- #
class AdminDepositAddressListCreateView(APIView):
    """GET/POST /api/admin/deposit-addresses/ """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        rows = DepositAddress.objects.select_related('network').order_by('network__sort_order', '-is_active')
        data = [
            {
                'id': row.pk,
                'network': row.network.code,
                'network_name': row.network.name,
                'asset': row.asset,
                'address': row.address,
                'is_active': row.is_active,
                'created_at': row.created_at,
            }
            for row in rows
        ]
        return Response({'success': True, 'message': 'OK', 'data': data})

    def post(self, request):
        payload = request.data or {}
        network_code = (payload.get('network') or '').strip().upper()
        address = (payload.get('address') or '').strip()
        network = Network.objects.filter(code=network_code).first()
        errors = {}
        if network is None:
            errors['network'] = ['Unknown network.']
        if not address:
            errors['address'] = ['Address is required.']
        if len(address) > 255:
            errors['address'] = ['Address is too long.']
        if errors:
            return Response(
                {'success': False, 'message': 'Please correct the highlighted fields.', 'errors': errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with db_transaction.atomic():
            # Address-change safety: deactivate the previous active address
            # for this network/asset, then activate the new one.
            DepositAddress.objects.filter(network=network, asset='USDT', is_active=True).update(is_active=False)
            row = DepositAddress.objects.create(
                network=network, asset='USDT', address=address, is_active=True,
            )
            from apps.core.models import AuditLog

            AuditLog.objects.create(
                actor_user=request.user,
                action=AuditLog.Action.CREATE,
                target_type='deposit_address',
                target_id=str(row.pk),
                description=f'Activated new {network.code}/USDT deposit address {address[:10]}…',
            )
        return Response(
            {
                'success': True,
                'message': 'Deposit address added and activated; previous address deactivated.',
                'data': {'id': row.pk, 'network': row.network.code, 'address': row.address, 'is_active': row.is_active},
            },
            status=status.HTTP_201_CREATED,
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class AdminDepositAddressDetailView(APIView):
    """PATCH /api/admin/deposit-addresses/<id>/ — edit / activate / deactivate."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, pk: int):
        row = DepositAddress.objects.filter(pk=pk).select_related('network').first()
        if row is None:
            return Response(
                {'success': False, 'message': 'Address not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload = request.data or {}
        changes = []

        if 'address' in payload:
            new_address = (payload.get('address') or '').strip()
            if not new_address:
                return Response(
                    {'success': False, 'message': 'Address cannot be empty.', 'errors': {'address': ['Address is required.']}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if new_address != row.address:
                row.address = new_address
                changes.append(f'address changed to {new_address[:10]}…')

        if 'is_active' in payload:
            desired = bool(payload.get('is_active'))
            if desired and not row.is_active:
                # Enforce one active address per network/asset.
                DepositAddress.objects.filter(
                    network=row.network, asset=row.asset, is_active=True,
                ).exclude(pk=row.pk).update(is_active=False)
                row.is_active = True
                changes.append('activated')
            elif not desired and row.is_active:
                row.is_active = False
                changes.append('deactivated')

        if changes:
            row.save()
            from apps.core.models import AuditLog

            AuditLog.objects.create(
                actor_user=request.user,
                action=AuditLog.Action.UPDATE,
                target_type='deposit_address',
                target_id=str(row.pk),
                description=f"{row.network.code}/USDT address {row.address[:10]}…: {', '.join(changes)}",
            )
        return Response(
            {
                'success': True,
                'message': 'Address updated.' if changes else 'No changes.',
                'data': {
                    'id': row.pk,
                    'network': row.network.code,
                    'address': row.address,
                    'is_active': row.is_active,
                },
            }
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class AdminNetworkListView(APIView):
    """GET/PATCH /api/admin/networks/ — network activation management."""

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        data = []
        for row in Network.objects.all().order_by('sort_order', 'code'):
            active = get_active_address(row)
            data.append(
                {
                    'id': row.pk,
                    'code': row.code,
                    'name': row.name,
                    'asset': row.asset,
                    'is_active': row.is_active,
                    'current_address': active.address if active else None,
                }
            )
        return Response({'success': True, 'message': 'OK', 'data': data})

    def patch(self, request, pk: int):
        row = Network.objects.filter(pk=pk).first()
        if row is None:
            return Response(
                {'success': False, 'message': 'Network not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        desired = bool((request.data or {}).get('is_active'))
        if row.is_active != desired:
            row.is_active = desired
            row.save(update_fields=['is_active'])
            from apps.core.models import AuditLog

            AuditLog.objects.create(
                actor_user=request.user,
                action=AuditLog.Action.UPDATE,
                target_type='network',
                target_id=str(row.pk),
                description=f'Network {row.code} {"activated" if desired else "deactivated"}.',
            )
        return Response(
            {
                'success': True,
                'message': 'Network updated.',
                'data': {'id': row.pk, 'code': row.code, 'is_active': row.is_active},
            }
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


__all__ = [
    'AdminDepositAddressDetailView',
    'AdminDepositAddressListCreateView',
    'AdminDepositDetailView',
    'AdminDepositListView',
    'AdminNetworkListView',
]
