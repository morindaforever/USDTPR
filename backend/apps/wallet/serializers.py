"""Serializers for the wallet app.

All monetary values serialize as fixed-point strings — never floats — so
precision survives the trip to the frontend intact.
"""

from rest_framework import serializers

from .models import Wallet, WalletTransaction


class WalletSummarySerializer(serializers.ModelSerializer):
    """Safe wallet representation for the dashboard."""

    total_balance = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    deposit_balance = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    withdrawable_balance = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    pending_balance = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    locked_balance = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    bonus_balance = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)

    class Meta:
        model = Wallet
        fields = [
            'total_balance',
            'deposit_balance',
            'withdrawable_balance',
            'pending_balance',
            'locked_balance',
            'bonus_balance',
        ]
        read_only_fields = fields


class WalletTransactionSerializer(serializers.ModelSerializer):
    """Ledger row for the owner's transaction history.

    ``type`` mirrors the API contract in docs/WALLET.md; the generic
    ``reference_type``/``reference_id`` pair points back at the business
    object that caused the movement (deposit, purchase, reward, …).
    """

    type = serializers.CharField(source='transaction_type', read_only=True)
    amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            'transaction_id',
            'type',
            'direction',
            'amount',
            'balance_type',
            'status',
            'description',
            'reference_type',
            'reference_id',
            'created_at',
        ]
        read_only_fields = fields
