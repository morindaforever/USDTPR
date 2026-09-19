"""Admin dashboard statistics (Section 12 §7–§9).

All aggregation happens in the database (Count/Sum over indexed date
ranges) — no full-table scans into the browser (§79), no client-side math
on financial values (§80). Financial metrics come from real aggregates.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from apps.deposits.models import Deposit
from apps.referrals.models import ReferralCommission
from apps.support.models import SupportConversation
from apps.vip.models import VIPPurchase, VIPReward
from apps.wallet.models import WalletTransaction
from apps.withdrawals.models import Withdrawal

from .permissions_config import ADMIN_GROUPS
from .serializers import AdminUserListSerializer
from .views import AdminAPIView, envelope

from django.contrib.auth import get_user_model

User = get_user_model()

RANGES = {
    'today': 1,
    '7d': 7,
    '30d': 30,
}


def _window(range_key: str, custom_from=None, custom_to=None):
    """Inclusive [start, end) window for the requested range; None = all."""
    now = timezone.now()
    if custom_from:
        start = timezone.make_aware(
            timezone.datetime.fromisoformat(str(custom_from) + 'T00:00:00')
        )
        end = timezone.make_aware(timezone.datetime.fromisoformat(str(custom_to or custom_from) + 'T23:59:59'))
        return start, end
    days = RANGES.get(range_key)
    if days is None:
        return None, None  # all time
    return now - timedelta(days=days), now


class AdminDashboardView(AdminAPIView):
    """GET /api/admin/dashboard/?range=today|7d|30d|all|custom&from=&to="""

    def get(self, request):
        range_key = (request.query_params.get('range') or 'all').lower()
        start, end = _window(range_key, request.query_params.get('from'), request.query_params.get('to'))

        def in_window(field: str):
            q = Q()
            if start is not None:
                q &= Q(**{f'{field}__gte': start})
                q &= Q(**{f'{field}__lt': end})
            return q

        users_qs = User.objects.all()
        totals = {
            'total_users': users_qs.count(),
            'active_users': users_qs.filter(account_status='ACTIVE', is_active=True).count(),
            'staff_users': users_qs.filter(is_staff=True).count(),
        }

        deposit_agg = Deposit.objects.filter(in_window('created_at')).aggregate(
            count=Count('id'), amount=Sum('amount'))
        withdrawal_agg = Withdrawal.objects.filter(in_window('created_at')).aggregate(
            count=Count('id'), amount=Sum('requested_amount'))
        reward_agg = VIPReward.objects.filter(in_window('created_at')).aggregate(
            count=Count('id'), credited=Sum('credited_amount'))
        commission_agg = ReferralCommission.objects.filter(in_window('created_at')).aggregate(
            count=Count('id'), amount=Sum('commission_amount'))
        purchase_agg = VIPPurchase.objects.filter(in_window('created_at')).aggregate(
            count=Count('id'), investment=Sum('investment_amount'))

        pending = {
            'pending_deposits': Deposit.objects.filter(status=Deposit.Status.PENDING).count(),
            'pending_withdrawals': Withdrawal.objects.filter(status=Withdrawal.Status.PENDING).count(),
            'open_support': SupportConversation.objects.exclude(
                status__in=[SupportConversation.Status.CLOSED]).count(),
            'active_vip_purchases': VIPPurchase.objects.filter(status='ACTIVE').count(),
        }

        # Registrations per day for the analytics chart (§9).
        registrations = []
        if start is not None:
            day = start.date()
            end_date = end.date()
            rows = (
                User.objects.filter(created_at__gte=start, created_at__lt=end)
                .values('created_at__date').annotate(count=Count('id'))
            )
            by_day = {row['created_at__date']: row['count'] for row in rows}
            while day <= end_date:
                registrations.append({'date': day.isoformat(), 'count': by_day.get(day, 0)})
                day += timedelta(days=1)

        def money(value) -> str:
            return str(Decimal(value or 0).quantize(Decimal('0.01')))

        data = {
            'range': range_key,
            **totals,
            'pending': pending,
            # Production conversion (§15/§16): these are REAL database
            # aggregates over actual deposits/withdrawals/purchases/rewards/
            # commissions — renamed from demo_metrics to financial_metrics.
            'financial_metrics': {
                'label': 'Platform financial activity (actual database records)',
                'deposits_submitted': {
                    'count': deposit_agg['count'] or 0,
                    'amount': money(deposit_agg['amount']),
                },
                'withdrawals_requested': {
                    'count': withdrawal_agg['count'] or 0,
                    'amount': money(withdrawal_agg['amount']),
                },
                'vip_purchases': {
                    'count': purchase_agg['count'] or 0,
                    'investment': money(purchase_agg['investment']),
                },
                'rewards_credited': {
                    'count': reward_agg['count'] or 0,
                    'amount': money(reward_agg['credited']),
                },
                'commissions_credited': {
                    'count': commission_agg['count'] or 0,
                    'amount': money(commission_agg['amount']),
                },
            },
            'registrations': registrations,
            'permission_groups': list(ADMIN_GROUPS.keys()),
            'recent_users': AdminUserListSerializer(
                User.objects.order_by('-created_at')[:5], many=True
            ).data,
        }
        return envelope(data)
