"""Referral API views (Section 9 §30–34).

All endpoints require authentication and return only the requesting user's
data (§57: user isolation). Team/commission lists use the wallet app's
EnvelopePagination convention. Errors use the standard
``{success, message, errors}`` envelope — stack traces never surface.
"""

from decimal import Decimal

from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.exceptions import api_exception_handler
from apps.vip.reward_service import current_cycle
from apps.wallet.pagination import EnvelopePagination

from . import config, tree
from .models import ReferralCommission
from .serializers import (
    ReferralCommissionSerializer,
    ReferralSummarySerializer,
    TeamMemberSerializer,
)


def _exception_context(view) -> dict:
    return {'view': view, 'request': getattr(view, 'request', None), 'args': (), 'kwargs': {}}


class _AuthedAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def handle_exception(self, exc):
        response = api_exception_handler(exc, _exception_context(self))
        if response is None:
            raise exc
        return response


def _team_queryset(user, level: int | None, status: str | None, search: str | None):
    """The user's team as (member_user, level) rows, bounded walk-free.

    Level N members are found by walking down level by level (N ≤ max 5);
    each hop is one indexed query on ``referred_by`` — no recursion.
    """
    ids_by_level: dict[int, list] = {}
    frontier = [user.id]
    max_level = config.get_max_level()
    wanted = [level] if level is not None else list(range(1, max_level + 1))
    for depth in range(1, max_level + 1):
        if depth not in wanted:
            # Still need to WALK through this level to reach deeper ones.
            rows = User.objects.filter(referred_by_id__in=frontier).values_list('id', flat=True)
            frontier = list(rows)
            if not frontier:
                break
            continue
        rows = User.objects.filter(referred_by_id__in=frontier).order_by('-created_at', 'id')
        page_ids = list(rows.values_list('id', flat=True)[:5000])
        ids_by_level[depth] = page_ids
        frontier = page_ids
        if not frontier:
            break

    combined: list[tuple[int, int]] = []
    for depth, ids in ids_by_level.items():
        combined.extend((pk, depth) for pk in ids)

    if status:
        wanted_status = status.upper()
    else:
        wanted_status = None
    if search:
        search = search.strip()

    members = User.objects.filter(id__in=[pk for pk, _ in combined])
    if wanted_status:
        members = members.filter(account_status=wanted_status)
    if search:
        members = members.filter(Q(user_id__iexact=search.upper()) | Q(full_name__icontains=search))

    level_by_pk = dict(combined)
    found = list(members)
    # Attach level from the walk (annotate-free; single fetch).
    results = []
    for member in sorted(found, key=lambda m: m.created_at, reverse=True):
        member.level = level_by_pk.get(member.id, 0)
        results.append(member)
    return results


class ReferralSummaryView(_AuthedAPIView):
    """GET /api/referrals/summary/ (§32)."""

    def get(self, request):
        user = request.user
        max_level = config.get_max_level()

        # Bounded level-by-level walk with counts aggregated in SQL.
        level_counts: dict[str, int] = {}
        active_by_level: dict[int, int] = {}
        frontier = [user.id]
        total = 0
        active_total = 0
        for depth in range(1, max_level + 1):
            rows = list(
                User.objects.filter(referred_by_id__in=frontier)
                .values('account_status')
                .annotate(n=Count('id'))
            )
            counts = {r['account_status']: r['n'] for r in rows}
            level_n = sum(counts.values())
            level_counts[str(depth)] = level_n
            active_by_level[depth] = counts.get(User.AccountStatus.ACTIVE, 0)
            total += level_n
            active_total += active_by_level[depth]
            if level_n == 0:
                # Deeper levels still possible through non-active members;
                # keep walking using their IDs.
                pass
            frontier = list(
                User.objects.filter(referred_by_id__in=frontier).values_list('id', flat=True)[:5000]
            )
            if not frontier:
                break

        agg = ReferralCommission.objects.filter(
            user=user, status=ReferralCommission.Status.CREDITED,
        ).aggregate(
            total=Coalesce(Sum('commission_amount'), Decimal('0')),
            this_cycle=Coalesce(
                Sum('commission_amount', filter=Q(cycle_date=current_cycle())),
                Decimal('0'),
            ),
        )
        by_level_rows = ReferralCommission.objects.filter(
            user=user, status=ReferralCommission.Status.CREDITED,
        ).values('level').annotate(total=Coalesce(Sum('commission_amount'), Decimal('0')))
        by_level = {str(r['level']): str(r['total'].quantize(Decimal('0.01'))) for r in by_level_rows}

        payload = {
            'referral_code': user.referral_code,
            'direct_referrals': level_counts.get('1', 0),
            'total_team': total,
            'active_team': active_total,
            'level_counts': level_counts,
            'commission_totals': {
                'total': str(agg['total'].quantize(Decimal('0.01'))),
                'this_cycle': str(agg['this_cycle'].quantize(Decimal('0.01'))),
                'by_level': by_level,
            },
            'max_level': max_level,
            'commission_rates': {
                str(level): str(rate.quantize(Decimal('0.01')))
                for level, rate in config.rates_snapshot().items()
            },
        }
        data = ReferralSummarySerializer(payload).data
        return Response({'success': True, 'message': 'OK', 'data': data})


class DirectReferralsView(_AuthedAPIView):
    """GET /api/referrals/direct/ — level 1 members only (§31)."""

    def get(self, request):
        members = _team_queryset(request.user, level=1, status=None, search=None)
        data = TeamMemberSerializer(
            [{'user_id': m.user_id, 'full_name': m.full_name, 'level': m.level,
              'account_status': m.account_status, 'created_at': m.created_at} for m in members],
            many=True,
        ).data
        return Response({'success': True, 'message': 'OK', 'data': data})


class TeamListView(_AuthedAPIView):
    """GET /api/referrals/team/?level=&status=&search= (§30, §51–53)."""

    def get(self, request):
        level_raw = request.query_params.get('level')
        status = request.query_params.get('status')
        search = request.query_params.get('search')
        level: int | None = None
        if level_raw:
            try:
                level = int(level_raw)
            except (TypeError, ValueError):
                return Response({'success': False, 'message': 'Invalid level filter.',
                                 'errors': {'level': ['Must be an integer.']}, 'data': None}, status=400)
            if level < 1 or level > config.get_max_level():
                return Response({'success': False, 'message': 'Level out of range.',
                                 'errors': {'level': [f'Must be 1..{config.get_max_level()}']}, 'data': None},
                                status=400)
        members = _team_queryset(request.user, level=level, status=status, search=search)

        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(members, request, view=self)
        data = TeamMemberSerializer(
            [{'user_id': m.user_id, 'full_name': m.full_name, 'level': m.level,
              'account_status': m.account_status, 'created_at': m.created_at} for m in page],
            many=True,
        ).data
        return paginator.get_paginated_response(data)


class CommissionListView(_AuthedAPIView):
    """GET /api/referrals/commissions/?level=&status= (§33)."""

    def get(self, request):
        qs = ReferralCommission.objects.filter(user=request.user).select_related(
            'source_user', 'source_reward', 'wallet_transaction',
        )
        level_raw = request.query_params.get('level')
        if level_raw:
            try:
                qs = qs.filter(level=int(level_raw))
            except (TypeError, ValueError):
                return Response({'success': False, 'message': 'Invalid level filter.',
                                 'errors': {'level': ['Must be an integer.']}, 'data': None}, status=400)
        status_raw = request.query_params.get('status')
        if status_raw:
            status = status_raw.upper()
            if status not in ReferralCommission.Status.values:
                return Response({'success': False, 'message': 'Invalid status filter.',
                                 'errors': {'status': ['Unknown status.']}, 'data': None}, status=400)
            qs = qs.filter(status=status)
        date_from = request.query_params.get('date_from')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        date_to = request.query_params.get('date_to')
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        paginator = EnvelopePagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = ReferralCommissionSerializer(page, many=True).data
        return paginator.get_paginated_response(data)


class CommissionDetailView(_AuthedAPIView):
    """GET /api/referrals/commissions/<commission_id>/ — owner-only (§34)."""

    def get(self, request, commission_id: str):
        commission = (
            ReferralCommission.objects.filter(user=request.user, commission_id=commission_id)
            .select_related('source_user', 'source_reward', 'wallet_transaction')
            .first()
        )
        if commission is None:
            # 404 (not 403) so IDs of other users' commissions are not
            # distinguishable from nonexistent ones (IDOR hardening, §57).
            return Response({'success': False, 'message': 'Commission not found.',
                             'errors': {}, 'data': None}, status=404)
        data = ReferralCommissionSerializer(commission).data
        return Response({'success': True, 'message': 'OK', 'data': data})
