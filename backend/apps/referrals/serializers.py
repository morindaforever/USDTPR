"""Serializers for the referrals API (Section 9).

Privacy (§29, §41): team members and commission counterparties are exposed
as public user IDs + display names only — never emails, phones, wallet
addresses, or authentication data. All money values serialize as strings.
"""

from decimal import Decimal
from urllib.parse import quote

from django.conf import settings as dj_settings
from rest_framework import serializers

from .models import Referral, ReferralCommission


class TeamMemberSerializer(serializers.Serializer):
    """One team member — the safe public projection of a User row."""

    user_id = serializers.CharField()
    full_name = serializers.CharField()
    level = serializers.IntegerField()
    status = serializers.CharField(source='account_status')
    joined_at = serializers.DateTimeField(source='created_at')


def build_referral_link(code: str) -> str:
    """Public signup link for a referral code (§4).

    Base URL comes from the PUBLIC_APP_URL environment setting — never a
    hard-coded production domain. The code is URL-encoded.
    """
    return f"{dj_settings.PUBLIC_APP_URL.rstrip('/')}/signup?ref={quote(code)}"


class ReferralSummarySerializer(serializers.Serializer):
    """GET /api/referrals/summary/ payload (§32) — all values computed from
    persisted rows; nothing invented client-side."""

    referral_code = serializers.CharField()
    referral_link = serializers.SerializerMethodField()
    direct_referrals = serializers.IntegerField()
    total_team = serializers.IntegerField()
    active_team = serializers.IntegerField()
    level_counts = serializers.DictField(child=serializers.IntegerField())
    # JSONField preserves the nested {total, this_cycle, by_level} shape —
    # a CharField child would coerce the whole dict to its str() repr.
    commission_totals = serializers.JSONField()
    max_level = serializers.IntegerField()
    commission_rates = serializers.DictField(child=serializers.CharField())

    def get_referral_link(self, obj) -> str:
        return build_referral_link(obj['referral_code'])


class ReferralCommissionSerializer(serializers.ModelSerializer):
    """One commission row for the owner's history (§33)."""

    source_user_id = serializers.CharField(source='source_user.user_id', read_only=True)
    reward_id = serializers.CharField(source='source_reward.reward_id', read_only=True)
    commission_rate_percent = serializers.SerializerMethodField()
    transaction_id = serializers.SerializerMethodField()

    class Meta:
        model = ReferralCommission
        fields = [
            'commission_id',
            'source_user_id',
            'level',
            'reward_id',
            'source_reward_amount',
            'commission_rate_percent',
            'commission_amount',
            'status',
            'cycle_date',
            'created_at',
            'processed_at',
            'transaction_id',
        ]
        read_only_fields = fields

    def get_commission_rate_percent(self, obj: ReferralCommission) -> str:
        # Stored as a fraction (0.10); displayed as a percent (10.00).
        return str((obj.commission_rate * Decimal('100')).quantize(Decimal('0.01')))

    def get_transaction_id(self, obj: ReferralCommission) -> str | None:
        return obj.wallet_transaction.transaction_id if obj.wallet_transaction else None
