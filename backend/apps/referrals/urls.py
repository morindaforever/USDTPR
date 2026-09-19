"""Referral API routes (Section 9 §30–34, §67)."""

from django.urls import path

from . import views

app_name = 'referrals'

urlpatterns = [
    path('summary/', views.ReferralSummaryView.as_view(), name='summary'),
    path('direct/', views.DirectReferralsView.as_view(), name='direct'),
    path('team/', views.TeamListView.as_view(), name='team'),
    path('commissions/', views.CommissionListView.as_view(), name='commissions'),
    path('commissions/<str:commission_id>/', views.CommissionDetailView.as_view(), name='commission-detail'),
]
