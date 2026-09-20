"""Serializers for the VIP app."""

from decimal import Decimal

from rest_framework import serializers

from .models import VIPPlan, VIPPurchase, VIPReward

_EIGHT_DP = Decimal('0.00000001')
_TWO_DP = Decimal('0.01')


class VIPPlanSerializer(serializers.ModelSerializer):
    """Plan card/detail data. All money serialized Decimal→string."""

    investment_amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    target_amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    daily_rate = serializers.DecimalField(max_digits=5, decimal_places=4, read_only=True)
    # daily_rate is a fraction (0.25); percent is a display convenience.
    daily_rate_percent = serializers.SerializerMethodField()
    profit_amount = serializers.SerializerMethodField()
    # Zero-investment promotional plan (name-based; see VIPPlan.is_welcome_plan).
    is_welcome_plan = serializers.SerializerMethodField()

    class Meta:
        model = VIPPlan
        fields = [
            'id',
            'plan_number',
            'name',
            'investment_amount',
            'target_amount',
            'daily_rate',
            'daily_rate_percent',
            'profit_amount',
            'is_welcome_plan',
            'is_active',
        ]
        read_only_fields = fields

    def get_daily_rate_percent(self, obj: VIPPlan) -> str:
        return str((obj.daily_rate * 100).quantize(_TWO_DP))

    def get_is_welcome_plan(self, obj: VIPPlan) -> bool:
        return obj.is_welcome_plan

    def get_profit_amount(self, obj: VIPPlan) -> str:
        return str((obj.target_amount - obj.investment_amount).quantize(_EIGHT_DP))


class CurrentPlanSerializer(serializers.ModelSerializer):
    """The user's active plan (Section 4 dashboard endpoint) with snapshot
    fields and progress data."""

    amount_received = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    investment_amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    target_amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    daily_rate_snapshot = serializers.DecimalField(max_digits=5, decimal_places=4, read_only=True)
    is_welcome_plan = serializers.SerializerMethodField()
    # Section 8 progress — same backend-authoritative numbers as /vip/active/.
    rewarded_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()
    next_reward_cycle = serializers.SerializerMethodField()
    next_reward_at = serializers.SerializerMethodField()

    class Meta:
        model = VIPPurchase
        fields = [
            'purchase_id',
            'plan_name_snapshot',
            'investment_amount',
            'target_amount',
            'daily_rate_snapshot',
            'amount_received',
            'status',
            'started_at',
            'is_welcome_plan',
            'rewarded_amount',
            'remaining_amount',
            'progress_percent',
            'next_reward_cycle',
            'next_reward_at',
        ]
        read_only_fields = fields

    def _progress(self, obj: VIPPurchase) -> dict:
        if not hasattr(obj, '_progress_cache'):
            from .reward_service import get_purchase_progress

            obj._progress_cache = get_purchase_progress(obj)
        return obj._progress_cache

    def get_rewarded_amount(self, obj: VIPPurchase) -> str:
        return self._progress(obj)['rewarded_amount']

    def get_remaining_amount(self, obj: VIPPurchase) -> str:
        return self._progress(obj)['remaining_amount']

    def get_progress_percent(self, obj: VIPPurchase) -> str:
        return self._progress(obj)['progress_percent']

    def get_next_reward_cycle(self, obj: VIPPurchase) -> str:
        return self._progress(obj)['next_reward_cycle']

    def get_next_reward_at(self, obj: VIPPurchase) -> str:
        return self._progress(obj)['next_reward_at']

    def get_is_welcome_plan(self, obj: VIPPurchase) -> bool:
        # Snapshot rows keep their meaning even if the plan row is edited.
        return obj.plan_name_snapshot.upper().startswith('WELCOME')


class VIPPurchaseSerializer(serializers.ModelSerializer):
    """The owner's purchase with its immutable term snapshot."""

    plan_name = serializers.CharField(source='plan_name_snapshot', read_only=True)
    investment_amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    target_amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    daily_rate = serializers.DecimalField(max_digits=5, decimal_places=4, source='daily_rate_snapshot', read_only=True)
    daily_rate_percent = serializers.SerializerMethodField()

    class Meta:
        model = VIPPurchase
        fields = [
            'purchase_id',
            'plan_name',
            'investment_amount',
            'target_amount',
            'daily_rate',
            'daily_rate_percent',
            'amount_received',
            'status',
            'started_at',
            'completed_at',
            'created_at',
        ]
        read_only_fields = fields

    def get_daily_rate_percent(self, obj: VIPPurchase) -> str:
        return str((obj.daily_rate_snapshot * 100).quantize(_TWO_DP))


class VIPRewardSerializer(serializers.ModelSerializer):
    """One reward cycle for the owner's history (§20).

    All money serialized Decimal→string; ``transaction_id`` exposes the
    linked ledger row so users can match rewards against wallet history.
    """

    plan_name = serializers.CharField(source='vip_purchase.plan_name_snapshot', read_only=True)
    purchase_id = serializers.CharField(source='vip_purchase.purchase_id', read_only=True)
    calculated_amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    credited_amount = serializers.DecimalField(max_digits=24, decimal_places=8, read_only=True)
    transaction_id = serializers.CharField(
        source='wallet_transaction.transaction_id', read_only=True, default=None,
    )

    class Meta:
        model = VIPReward
        fields = [
            'reward_id',
            'purchase_id',
            'plan_name',
            'reward_date',
            'calculated_amount',
            'credited_amount',
            'status',
            'transaction_id',
            'created_at',
            'processed_at',
        ]
        read_only_fields = fields


class VIPPurchaseProgressSerializer(VIPPurchaseSerializer):
    """Active/completed purchase with backend-computed reward progress (§22).

    ``rewarded_amount`` comes from the aggregated successful-reward sum the
    view annotates — never from the frontend. ``remaining_amount`` never
    goes negative; ``progress_percent`` caps at 100 (§23).
    """

    rewarded_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()
    next_reward_cycle = serializers.SerializerMethodField()

    class Meta(VIPPurchaseSerializer.Meta):
        fields = VIPPurchaseSerializer.Meta.fields + [
            'rewarded_amount',
            'remaining_amount',
            'progress_percent',
            'next_reward_cycle',
        ]

    def _progress(self, obj) -> dict:
        if not hasattr(obj, '_progress_cache'):
            from .reward_service import get_purchase_progress

            # Annotated rows carry the aggregated rewarded sum — no extra query.
            rewarded = getattr(obj, 'rewarded_amount_annotated', None)
            obj._progress_cache = get_purchase_progress(obj, rewarded)
        return obj._progress_cache

    def get_rewarded_amount(self, obj) -> str:
        return self._progress(obj)['rewarded_amount']

    def get_remaining_amount(self, obj) -> str:
        return self._progress(obj)['remaining_amount']

    def get_progress_percent(self, obj) -> str:
        return self._progress(obj)['progress_percent']

    def get_next_reward_cycle(self, obj) -> str:
        return self._progress(obj)['next_reward_cycle']
