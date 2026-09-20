"""Serializers for the deposit app."""

from rest_framework import serializers

from .models import Deposit


class NetworkSerializer(serializers.Serializer):
    """Active network option for the deposit page (per-network config)."""

    code = serializers.CharField()
    name = serializers.CharField()
    asset = serializers.CharField()
    contract_address = serializers.CharField(allow_blank=True)
    minimum_amount = serializers.CharField()
    network_warning = serializers.CharField(allow_blank=True)
    instructions = serializers.CharField(allow_blank=True)
    has_address = serializers.BooleanField()


class DepositAddressSerializer(serializers.Serializer):
    network = serializers.CharField()
    asset = serializers.CharField()
    address = serializers.CharField()
    qr_code = serializers.CharField(allow_null=True)


class DepositSerializer(serializers.ModelSerializer):
    """The owner's deposit view (user-safe fields only)."""

    network = serializers.CharField(source='network.code', read_only=True)
    network_name = serializers.CharField(source='network.name', read_only=True)
    has_screenshot = serializers.SerializerMethodField()

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
            'has_screenshot',
            'status',
            'admin_note',
            'submitted_at',
            'approved_at',
            'rejected_at',
            'created_at',
        ]
        read_only_fields = fields

    def get_has_screenshot(self, deposit: Deposit) -> bool:
        return bool(deposit.screenshot)


class SubmitDepositSerializer(serializers.Serializer):
    """POST /api/deposits/ payload (JSON, or multipart with a screenshot)."""

    network = serializers.CharField(max_length=10)
    amount = serializers.CharField(max_length=32)
    tx_hash = serializers.CharField(max_length=128, required=False, allow_blank=True, default='')
    order_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default='')
    screenshot = serializers.ImageField(
        required=False,
        allow_null=True,
        help_text='Optional payment screenshot (PNG/JPEG/WebP, size-limited).',
    )

    def validate(self, attrs):
        # An explicitly empty multipart file field (browser sends '') means
        # "no screenshot", not "invalid image".
        screenshot = attrs.get('screenshot')
        if screenshot is not None and hasattr(screenshot, 'name') and not screenshot.name:
            attrs['screenshot'] = None
        return attrs


class AdminDepositSerializer(serializers.ModelSerializer):
    """Admin list/detail — adds reviewer, screenshot flag, verification info."""

    network = serializers.CharField(source='network.code', read_only=True)
    network_name = serializers.CharField(source='network.name', read_only=True)
    user_id = serializers.CharField(source='user.user_id', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    reviewer_email = serializers.EmailField(source='reviewed_by.email', read_only=True, allow_null=True)
    has_screenshot = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()
    reviewed_at = serializers.SerializerMethodField()

    class Meta:
        model = Deposit
        fields = [
            'deposit_id',
            'user_id',
            'user_email',
            'network',
            'network_name',
            'asset',
            'amount',
            'tx_hash',
            'order_id',
            'deposit_address',
            'has_screenshot',
            'status',
            'admin_note',
            'submitted_at',
            'approved_at',
            'rejected_at',
            'reviewed_at',
            'reviewer_email',
            'verified_at',
            'verification_note',
            'verification_status',
            'created_at',
        ]
        read_only_fields = fields

    def get_has_screenshot(self, deposit: Deposit) -> bool:
        return bool(deposit.screenshot)

    def get_reviewed_at(self, deposit: Deposit):
        return deposit.approved_at or deposit.rejected_at

    def get_verification_status(self, deposit: Deposit) -> str:
        """Honest label: on-chain verified only when a real provider ran."""
        if deposit.verified_at:
            return 'ON_CHAIN_VERIFIED'
        return 'MANUAL_VERIFICATION'
