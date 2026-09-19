"""Core API routes: cross-cutting endpoints only."""

from django.urls import path

from .views import SiteStatusView, ValuationView, health

app_name = 'core'

urlpatterns = [
    path('health/', health, name='health'),
    path('site/status/', SiteStatusView.as_view(), name='site-status'),
    path('site/valuation/', ValuationView.as_view(), name='valuation'),
]
