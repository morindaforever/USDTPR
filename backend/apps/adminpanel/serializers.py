"""Admin serializers (Section 12).

Read serializers project only what the admin UI needs — never password
fields, tokens, or secret metadata (§17, §81). Write serializers explicitly
whitelist editable fields so mass assignment of is_staff/is_superuser/
account_status is impossible (§71, §100–101).
"""

from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.accounts.models import LoginActivity
from apps.core.models import AuditLog, SiteSetting
from apps.deposits.models import Deposit
from apps.notifications.models import Notification
from apps.referrals.models import Referral, ReferralCommission
from apps.support.models import SupportConversation, SupportMessage
from apps.vip.models import VIPPlan, VIPPurchase, VIPReward
from apps.wallet.models import Wallet, WalletTransaction
from apps.withdrawals.models import Withdrawal

User = get_user_model()


class AdminUserListSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'user_id', 'full_name', 'email', 'phone', 'account_status',
            'kyc_status', 'is_staff', 'created_at',
        ]
        read_only_fields = fields


class AdminWalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = [
            'total_balance', 'deposit_balance', 'withdrawable_balance',
            'pending_balance', 'locked_balance', 'bonus_balance',
        ]
        read_only_fields = fields


class AdminUserDetailSerializer(serializers.ModelSerializer):
    wallet = AdminWalletSerializer(read_only=True)
    direct_referrals_count = serializers.SerializerMethodField()
    last_login = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'user_id', 'full_name', 'email', 'phone', 'account_status',
            'kyc_status', 'kyc_verified_at', 'is_staff', 'referral_code',
            'created_at', 'last_login', 'wallet', 'direct_referrals_count',
        ]
        read_only_fields = fields

    def get_direct_referrals_count(self, obj) -> int:
        return obj.direct_referrals.count()

    def get_last_login(self, obj):
        latest = obj.login_activities.filter(outcome=LoginActivity.Outcome.SUCCESS).order_by('-created_at').first()
        return latest.created_at if latest else None


class AdminUserActionSerializer(serializers.Serializer):
    """Payload for suspend/ban/activate — reason required for suspend/ban."""

    reason = serializers.CharField(max_length=500, required=False, allow_blank=True, default='')

    def validate(self, attrs):
        action = self.context.get('action')
        if action in ('suspend', 'ban') and not (attrs.get('reason') or '').strip():
            raise serializers.ValidationError(
                {'reason': ['A reason is required to suspend or ban a user.']}
            )
        return attrs


class AdminVIPPlanSerializer(serializers.ModelSerializer):
    """Plan write serializer — explicit whitelist only (§31–32)."""

    investment_amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal('0.01'))
    target_amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal('0.01'))
    daily_rate = serializers.DecimalField(max_digits=5, decimal_places=4, min_value=Decimal('0.0001'), max_value=Decimal('1.0000'))

    class Meta:
        model = VIPPlan
        fields = [
            'id', 'name', 'plan_number', 'investment_amount', 'target_amount',
            'daily_rate', 'is_active', 'sort_order',
        ]

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError('Plan name is required.')
        qs = VIPPlan.objects.exclude(pk=self.instance.pk if self.instance else None)
        if qs.filter(name__iexact=cleaned).exists():
            raise serializers.ValidationError('A plan with this name already exists.')
        return cleaned

    def validate(self, attrs):
        target = attrs.get('target_amount', getattr(self.instance, 'target_amount', None))
        investment = attrs.get('investment_amount', getattr(self.instance, 'investment_amount', None))
        if target is not None and investment is not None and target <= investment:
            raise serializers.ValidationError(
                {'target_amount': ['Target amount must exceed the investment amount.']}
            )
        return attrs


class AdminVIPPlanListSerializer(serializers.ModelSerializer):
    class Meta:
        model = VIPPlan
        fields = [
            'id', 'name', 'plan_number', 'investment_amount', 'target_amount',
            'daily_rate', 'is_active', 'sort_order',
        ]
        read_only_fields = fields


class AdminVIPPurchaseSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.user_id', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    rewarded_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()

    class Meta:
        model = VIPPurchase
        fields = [
            'purchase_id', 'user_id', 'user_email', 'plan_name_snapshot',
            'investment_amount', 'target_amount', 'daily_rate_snapshot',
            'rewarded_amount', 'remaining_amount', 'status', 'started_at', 'created_at',
        ]
        read_only_fields = fields

    def get_rewarded_amount(self, obj) -> str:
        from apps.vip.reward_service import get_rewarded_amount
        return str(get_rewarded_amount(obj).quantize(Decimal('0.01')))

    def get_remaining_amount(self, obj) -> str:
        from apps.vip.reward_service import get_remaining_target
        return str(get_remaining_target(obj).quantize(Decimal('0.01')))


class AdminVIPRewardSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.user_id', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    purchase_id = serializers.CharField(source='vip_purchase.purchase_id', read_only=True)

    class Meta:
        model = VIPReward
        fields = [
            'reward_id', 'user_id', 'user_email', 'purchase_id', 'reward_date',
            'calculated_amount', 'credited_amount', 'status', 'error_info', 'created_at',
        ]
        read_only_fields = fields


class AdminReferralSerializer(serializers.ModelSerializer):
    """One downstream relationship (referrer → referred)."""

    referrer_id = serializers.CharField(source='referrer.user_id', read_only=True)
    referrer_email = serializers.CharField(source='referrer.email', read_only=True)
    referred_id = serializers.CharField(source='referred_user.user_id', read_only=True)
    referred_email = serializers.CharField(source='referred_user.email', read_only=True)

    class Meta:
        model = Referral
        fields = [
            'id', 'referrer_id', 'referrer_email', 'referred_id',
            'referred_email', 'status', 'created_at',
        ]
        read_only_fields = fields


class AdminCommissionSerializer(serializers.ModelSerializer):
    beneficiary_id = serializers.CharField(source='user.user_id', read_only=True)
    beneficiary_email = serializers.CharField(source='user.email', read_only=True)
    source_user_id = serializers.CharField(source='source_user.user_id', read_only=True)

    class Meta:
        model = ReferralCommission
        fields = [
            'commission_id', 'beneficiary_id', 'beneficiary_email', 'source_user_id',
            'level', 'commission_rate', 'source_reward_amount', 'commission_amount',
            'status', 'created_at',
        ]
        read_only_fields = fields


class AdminTransactionSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.user_id', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)

    class Meta:
        model = WalletTransaction
        fields = [
            'transaction_id', 'user_id', 'user_email', 'transaction_type',
            'direction', 'balance_type', 'amount', 'status', 'reference_type',
            'reference_id', 'description', 'created_at',
        ]
        read_only_fields = fields


class AdminNotificationSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.user_id', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'user_id', 'notification_type', 'title', 'message',
            'is_read', 'created_at', 'read_at',
        ]
        read_only_fields = fields


class AdminAuditLogSerializer(serializers.ModelSerializer):
    actor_id = serializers.CharField(source='actor_user.user_id', read_only=True)
    actor_email = serializers.CharField(source='actor_user.email', read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            'id', 'actor_id', 'actor_email', 'action', 'target_type',
            'target_id', 'description', 'ip_address', 'created_at',
        ]
        read_only_fields = fields


class AdminSupportConversationListSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.user_id', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    message_count = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()

    class Meta:
        model = SupportConversation
        fields = [
            'conversation_id', 'user_id', 'user_email', 'subject', 'status',
            'priority', 'created_at', 'updated_at', 'message_count', 'last_message_preview',
        ]
        read_only_fields = fields

    def get_message_count(self, obj) -> int:
        return obj.messages.count()

    def get_last_message_preview(self, obj) -> str:
        row = obj.messages.order_by('-created_at').first()
        if row is None:
            return ''
        preview = ' '.join(row.message.split())
        return preview[:120] + ('…' if len(preview) > 120 else '')


class AdminSupportMessageSerializer(serializers.ModelSerializer):
    sender_id = serializers.CharField(source='sender.user_id', read_only=True)
    sender_type = serializers.SerializerMethodField()

    class Meta:
        model = SupportMessage
        fields = ['id', 'sender_id', 'sender_type', 'message', 'created_at']
        read_only_fields = fields

    def get_sender_type(self, obj) -> str:
        return 'support' if obj.is_admin else 'user'


class AdminSupportConversationDetailSerializer(serializers.ModelSerializer):
    user_id = serializers.CharField(source='user.user_id', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    messages = serializers.SerializerMethodField()

    class Meta:
        model = SupportConversation
        fields = [
            'conversation_id', 'user_id', 'user_email', 'subject', 'status',
            'priority', 'created_at', 'updated_at', 'closed_at', 'messages',
        ]
        read_only_fields = fields

    def get_messages(self, obj) -> list:
        rows = obj.messages.all()[:300]
        return AdminSupportMessageSerializer(rows, many=True).data


class AdminSupportReplySerializer(serializers.Serializer):
    message = serializers.CharField(max_length=5000, required=True)


class AdminSupportStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SupportConversation.Status.choices, required=True)


class AdminSiteSettingSerializer(serializers.ModelSerializer):
    """Settings read/write. Key is immutable after creation (§63)."""

    group = serializers.SerializerMethodField()

    class Meta:
        model = SiteSetting
        fields = ['key', 'value', 'value_type', 'description', 'group']
        read_only_fields = ['key', 'value_type']

    def get_group(self, obj) -> str:
        prefix = obj.key.split('.', 1)[0] if '.' in obj.key else 'general'
        return prefix if prefix != 'platform' else 'general'

    def validate_value(self, value: str) -> str:
        # PATCH payloads identify the row by key; resolve its declared type.
        if self.instance is not None:
            value_type = self.instance.value_type
        else:
            key = (self.initial_data or {}).get('key', '')
            value_type = (
                SiteSetting.objects.filter(key=key).values_list('value_type', flat=True).first()
                or 'string'
            )
        if value_type == 'integer':
            try:
                int(value)
            except (TypeError, ValueError) as exc:
                raise serializers.ValidationError('Value must be an integer.') from exc
        elif value_type == 'decimal':
            try:
                Decimal(value)
            except (InvalidOperation, TypeError) as exc:
                raise serializers.ValidationError('Value must be a decimal number.') from exc
        elif value_type == 'boolean' and value.lower() not in ('true', 'false'):
            raise serializers.ValidationError("Value must be 'true' or 'false'.")
        return value
