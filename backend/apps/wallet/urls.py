"""Wallet API routes (read-only; mutations stay internal services)."""

from django.urls import path

from . import views

app_name = 'wallet'

urlpatterns = [
    path('summary/', views.WalletSummaryView.as_view(), name='summary'),
    path('transactions/', views.TransactionListView.as_view(), name='transactions'),
    path('transactions/<str:transaction_id>/', views.TransactionDetailView.as_view(), name='transaction-detail'),
]
