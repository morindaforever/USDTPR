"""Serializers for the withdrawals app.

User serializers mask the destination address in list views (§40) and never
expose admin-only fields (admin, admin_note, idempotency_key). The detail
serializer may show the full address to the owner.
"""

from rest_framework import serializers

from .models import Withdrawal


def mask_address(address: str) -> str:
    """``TQ8x…91Kz`` style masking for list views (§40)."""
    if not address:
        return ''
    if len(address) <= 10:
        return address[:2] + '…' + address[-2:] if len(address) > 6 else address
    return f'{address[:6]}…{address[-4:]}'


class WithdrawalListSerializer(serializers.ModelSerializer):
    network = serializers.CharField(source='network.code', read_only=True)
    network_name = serializers.CharField(source='network.name', read_only=True)
    masked_address = serializers.SerializerMethodField()
    amount = serializers.DecimalField(
        source='requested_amount', max_digits=24, decimal_places=8, read_only=True,
    )

    class Meta:
        model = Withdrawal
        fields = [
            'withdrawal_id',
            'network',
            'network_name',
            'masked_address',
            'amount',
            'fee_amount',
            'net_amount',
            'status',
            'tx_hash',
            'created_at',
            'completed_at',
        ]
        read_only_fields = fields

    def get_masked_address(self, obj: Withdrawal) -> str:
        return mask_address(obj.wallet_address)


class WithdrawalDetailSerializer(WithdrawalListSerializer):
    """Owner detail: full destination, rejection reason, real timestamps."""

    class Meta(WithdrawalListSerializer.Meta):
        fields = WithdrawalListSerializer.Meta.fields + [
            'destination_address',
            'rejection_reason',
            'approved_at',
            'rejected_at',
            'processing_at',
            'failed_at',
        ]

    destination_address = serializers.CharField(source='wallet_address', read_only=True)


class WithdrawalAdminSerializer(serializers.ModelSerializer):
    """Admin list/detail — full address and internal fields (is_staff only)."""

    network = serializers.CharField(source='network.code', read_only=True)
    user_id = serializers.CharField(source='user.user_id', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    amount = serializers.DecimalField(
        source='requested_amount', max_digits=24, decimal_places=8, read_only=True,
    )

    class Meta:
        model = Withdrawal
        fields = [
            'withdrawal_id',
            'user_id',
            'user_email',
            'network',
            'wallet_address',
            'amount',
            'fee_amount',
            'net_amount',
            'status',
            'tx_hash',
            'rejection_reason',
            'admin_note',
            'created_at',
            'approved_at',
            'rejected_at',
            'processing_at',
            'completed_at',
            'failed_at',
        ]
        read_only_fields = fields


class WithdrawalCreateSerializer(serializers.Serializer):
    """POST /api/withdrawals/ body (§18). Everything else is server-side."""

    network = serializers.CharField(max_length=10)
    destination_address = serializers.CharField(max_length=255)
    amount = serializers.DecimalField(max_digits=24, decimal_places=8)
    idempotency_key = serializers.CharField(max_length=128)


class WithdrawalQuoteSerializer(serializers.Serializer):
    """POST /api/withdrawals/quote/ body (§47)."""

    network = serializers.CharField(max_length=10, required=False, allow_blank=True)
    amount = serializers.DecimalField(max_digits=24, decimal_places=8)
