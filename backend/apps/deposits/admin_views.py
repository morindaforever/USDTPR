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
from .serializers import AdminDepositSerializer, DepositSerializer
from .services import approve_deposit, get_active_address, reject_deposit


def _exception_context(view) -> dict:
    return {'view': view, 'request': getattr(view, 'request', None), 'args': (), 'kwargs': {}}


class AdminDepositListView(ListAPIView):
    """GET /api/admin/deposits/ — filterable, paginated deposit list.

    Filters: status, network (code), user (public user ID), deposit_id,
    tx_hash, date_from/date_to (inclusive). Paginated 20/page.
    """

    serializer_class = AdminDepositSerializer
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

    serializer_class = AdminDepositSerializer
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
                'data': AdminDepositSerializer(deposit).data,
            }
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class AdminDepositApproveView(AdminDepositActionView):
    def post(self, request, deposit_id: str):  # pragma: no cover - delegates
        return super().post(request, deposit_id, 'approve')


class AdminDepositNoteView(APIView):
    """PATCH /api/admin/deposits/<deposit_id>/note/ — reviewer note only.

    Lets an admin record review context on any deposit without changing its
    status. Approved/rejected deposits are immutable except for this note
    (§2: editing an approved deposit must not alter financial terms).
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def patch(self, request, deposit_id: str):
        deposit = Deposit.objects.filter(deposit_id=deposit_id).first()
        if deposit is None:
            return Response(
                {'success': False, 'message': 'Deposit not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        note = ((request.data or {}).get('admin_note') or '').strip()
        if len(note) > 2000:
            return Response(
                {'success': False, 'message': 'Note is too long (max 2000 characters).', 'errors': {}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deposit.admin_note = note
        deposit.save(update_fields=['admin_note', 'updated_at'])
        from apps.core.models import AuditLog

        AuditLog.objects.create(
            actor_user=request.user,
            action=AuditLog.Action.UPDATE,
            target_type='deposit',
            target_id=deposit.deposit_id,
            description=f'Admin note updated on deposit {deposit.deposit_id}.',
        )
        return Response(
            {'success': True, 'message': 'Note saved.', 'data': AdminDepositSerializer(deposit).data}
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


class AdminDepositScreenshotView(APIView):
    """GET /api/admin/deposits/<deposit_id>/screenshot/ — staff-only image.

    Private-media proxy: the file is never on a public static path.
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request, deposit_id: str):
        deposit = Deposit.objects.filter(deposit_id=deposit_id).first()
        if deposit is None or not deposit.screenshot:
            return Response(
                {'success': False, 'message': 'Screenshot not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        from django.core.files.storage import default_storage

        if not default_storage.exists(deposit.screenshot.name):
            return Response(
                {'success': False, 'message': 'Screenshot file is missing.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        with default_storage.open(deposit.screenshot.name, 'rb') as handle:
            from django.http import FileResponse

            return FileResponse(handle, content_type='application/octet-stream')

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


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
    """GET/PATCH /api/admin/networks/ — network configuration management.

    GET exposes the full per-network configuration; PATCH accepts any
    subset of is_active/name/contract_address/min_deposit/min_withdrawal/
    withdrawal_fee/withdrawal_fee_is_percent/network_warning/instructions.
    Everything here is public display or business-rule configuration — no
    secrets are ever stored on Network rows (§8).
    """

    permission_classes = [IsAuthenticated, IsAdminUser]

    MONEY_FIELDS = {
        'min_deposit': 'min_deposit',
        'min_withdrawal': 'min_withdrawal',
        'withdrawal_fee': 'withdrawal_fee',
    }

    @staticmethod
    def _serialize_network(row: Network) -> dict:
        active = get_active_address(row)
        return {
            'id': row.pk,
            'code': row.code,
            'name': row.name,
            'asset': row.asset,
            'is_active': row.is_active,
            'current_address': active.address if active else None,
            'contract_address': row.contract_address,
            'min_deposit': str(row.min_deposit) if row.min_deposit is not None else None,
            'min_withdrawal': str(row.min_withdrawal) if row.min_withdrawal is not None else None,
            'withdrawal_fee': str(row.withdrawal_fee) if row.withdrawal_fee is not None else None,
            'withdrawal_fee_is_percent': row.withdrawal_fee_is_percent,
            'network_warning': row.network_warning,
            'instructions': row.instructions,
        }

    def get(self, request):
        data = [self._serialize_network(row) for row in Network.objects.all().order_by('sort_order', 'code')]
        return Response({'success': True, 'message': 'OK', 'data': data})

    def patch(self, request, pk: int):
        row = Network.objects.filter(pk=pk).first()
        if row is None:
            return Response(
                {'success': False, 'message': 'Network not found.', 'errors': {}},
                status=status.HTTP_404_NOT_FOUND,
            )
        payload = request.data or {}
        changes = []
        errors = {}

        if 'name' in payload:
            name = (payload.get('name') or '').strip()
            if not name:
                errors['name'] = ['Name cannot be empty.']
            elif name != row.name:
                row.name = name
                changes.append('name')

        if 'is_active' in payload:
            desired = bool(payload.get('is_active'))
            if row.is_active != desired:
                row.is_active = desired
                changes.append('activated' if desired else 'deactivated')

        if 'contract_address' in payload:
            contract = (payload.get('contract_address') or '').strip()
            if len(contract) > 255:
                errors['contract_address'] = ['Too long (max 255 characters).']
            elif contract != row.contract_address:
                row.contract_address = contract
                changes.append('contract_address')

        for payload_key, field in self.MONEY_FIELDS.items():
            if payload_key not in payload:
                continue
            raw = (payload.get(payload_key) or '').strip()
            if raw == '':
                if getattr(row, field) is not None:
                    setattr(row, field, None)  # clear → inherit global rule
                    changes.append(f'{payload_key} cleared (inherits global default)')
                continue
            from decimal import Decimal, InvalidOperation

            try:
                value = Decimal(raw)
            except InvalidOperation:
                errors[payload_key] = ['Must be a decimal number or empty.']
                continue
            if value <= 0 and payload_key != 'withdrawal_fee':
                errors[payload_key] = ['Must be greater than zero (or empty to inherit the default).']
                continue
            if value < 0:
                errors[payload_key] = ['Cannot be negative (or empty to inherit the default).']
                continue
            if getattr(row, field) != value:
                setattr(row, field, value)
                changes.append(payload_key)

        if 'withdrawal_fee_is_percent' in payload:
            raw = payload.get('withdrawal_fee_is_percent')
            if raw in ('', None):
                desired = None
            elif isinstance(raw, bool):
                desired = raw
            else:
                desired = str(raw).strip().lower() in ('true', '1', 'yes')
            if row.withdrawal_fee_is_percent != desired:
                row.withdrawal_fee_is_percent = desired
                changes.append('withdrawal_fee_is_percent')

        for text_field in ('network_warning', 'instructions'):
            if text_field in payload:
                value = (payload.get(text_field) or '').strip()
                if len(value) > (500 if text_field == 'network_warning' else 4000):
                    errors[text_field] = ['Too long.']
                elif value != getattr(row, text_field):
                    setattr(row, text_field, value)
                    changes.append(text_field)

        if errors:
            return Response(
                {'success': False, 'message': 'Please correct the highlighted fields.', 'errors': errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if changes:
            row.save()
            from apps.core.models import AuditLog

            AuditLog.objects.create(
                actor_user=request.user,
                action=AuditLog.Action.UPDATE,
                target_type='network',
                target_id=str(row.pk),
                description=f'Network {row.code} updated: {", ".join(changes)}.',
            )
        return Response(
            {
                'success': True,
                'message': 'Network updated.' if changes else 'No changes.',
                'data': self._serialize_network(row),
            }
        )

    def handle_exception(self, exc):
        return api_exception_handler(exc, _exception_context(self))


__all__ = [
    'AdminDepositAddressDetailView',
    'AdminDepositAddressListCreateView',
    'AdminDepositDetailView',
    'AdminDepositListView',
    'AdminDepositNoteView',
    'AdminDepositScreenshotView',
    'AdminNetworkListView',
]
