"""Serializers for the deposit app."""

from rest_framework import serializers

from .models import Deposit


class NetworkSerializer(serializers.Serializer):
    """Active network option for the deposit page."""

    code = serializers.CharField()
    name = serializers.CharField()
    asset = serializers.CharField()


class DepositAddressSerializer(serializers.Serializer):
    network = serializers.CharField()
    asset = serializers.CharField()
    address = serializers.CharField()
    qr_code = serializers.CharField(allow_null=True)


class DepositSerializer(serializers.ModelSerializer):
    """The owner's deposit view (user-safe fields only)."""

    network = serializers.CharField(source='network.code', read_only=True)
    network_name = serializers.CharField(source='network.name', read_only=True)

    class Meta:
        model = Deposit
        fields = [
            'deposit_id',
            'network',
            'network_name',
            'asset',
            'amount',
            'tx_hash',
            'order_id',
            'deposit_address',
            'status',
            'admin_note',
            'submitted_at',
            'approved_at',
            'rejected_at',
            'created_at',
        ]
        read_only_fields = fields


class SubmitDepositSerializer(serializers.Serializer):
    """POST /api/deposits/ payload."""

    network = serializers.CharField(max_length=10)
    amount = serializers.CharField(max_length=32)
    tx_hash = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')
    order_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
