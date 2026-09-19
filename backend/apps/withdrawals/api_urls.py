"""Section 10 withdrawal API routes (user-facing).

Mounted at ``/api/withdrawals/``. (The retired simulated-activity feed was
``apps.withdrawals.urls`` at ``/api/activity/`` — the two never mixed (§83).)
"""

from django.urls import path

from . import views

app_name = 'withdrawals-api'

urlpatterns = [
    path('networks/', views.NetworkListView.as_view(), name='networks'),
    path('rules/', views.RulesView.as_view(), name='rules'),
    path('summary/', views.WithdrawalSummaryView.as_view(), name='summary'),
    path('quote/', views.QuoteView.as_view(), name='quote'),
    path('', views.WithdrawalListCreateView.as_view(), name='list-create'),
    path('<str:withdrawal_id>/', views.WithdrawalDetailView.as_view(), name='detail'),
]
