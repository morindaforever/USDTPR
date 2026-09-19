"""Core API views shared by all sections."""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import api_exception_handler

from .models import CompanyValuation
from .serializers import CompanyValuationSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    """
    Liveness probe for the backend.

    Returns ``{"status": "ok"}`` when the API is serving. Database/Redis
    probes arrive with their sections; this stays dependency-free on
    purpose so it works even during infrastructure outages.
    """
    return Response({'status': 'ok'})


class SiteStatusView(APIView):
    """GET /api/site/status/ — public platform flags (Section 15 §37).

    Reads the admin-managed ``platform.maintenance_mode`` SiteSetting. Safe
    to expose: returns only a boolean flag, never setting values or
    internals. The frontend renders a maintenance notice from this flag —
    the switch itself lives in the admin panel, not in the client.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        from .models import SiteSetting

        raw = SiteSetting.objects.filter(key='platform.maintenance_mode').values_list(
            'value', flat=True
        ).first()
        maintenance = str(raw).strip().lower() in ('true', '1', 'yes')
        return Response({'success': True, 'message': 'OK', 'data': {'maintenance': maintenance}})

    def handle_exception(self, exc):
        return api_exception_handler(
            exc,
            {'view': self, 'request': getattr(self, 'request', None), 'args': (), 'kwargs': {}},
        )


class ValuationView(APIView):
    """GET /api/site/valuation/ — daily platform valuation series.

    Legacy endpoint retained for data access only; the production frontend
    no longer renders this series. Any rows still flagged ``is_demo`` are
    development seed data and are excluded from responses.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        rows = CompanyValuation.objects.filter(is_demo=False).order_by('valuation_date')
        data = CompanyValuationSerializer(rows, many=True).data
        return Response(
            {
                'success': True,
                'message': 'OK',
                'data': {'currency': data[0]['currency'] if data else 'USDT', 'data': data},
            }
        )

    def handle_exception(self, exc):
        return api_exception_handler(
            exc,
            {'view': self, 'request': getattr(self, 'request', None), 'args': (), 'kwargs': {}},
        )


__all__ = ['health', 'SiteStatusView', 'ValuationView']
