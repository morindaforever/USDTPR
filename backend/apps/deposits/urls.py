"""Deposit API routes (user-facing)."""

from django.urls import path

from . import views

app_name = 'deposits'

urlpatterns = [
    path('networks/', views.NetworkListView.as_view(), name='networks'),
    path('rules/', views.DepositRulesView.as_view(), name='rules'),
    path('address/', views.DepositAddressView.as_view(), name='address'),
    # GET = own deposit history, POST = submit a new deposit request.
    path('', views.DepositCollectionView.as_view(), name='deposits'),
    path('<str:deposit_id>/', views.DepositDetailView.as_view(), name='detail'),
]
