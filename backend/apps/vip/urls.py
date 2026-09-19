"""VIP API routes."""

from django.urls import path

from . import views

app_name = 'vip'

urlpatterns = [
    path('plans/', views.PlanListView.as_view(), name='plans'),
    path('plans/<int:plan_id>/', views.PlanDetailView.as_view(), name='plan-detail'),
    path('plans/<int:plan_id>/summary/', views.PlanSummaryView.as_view(), name='plan-summary'),
    path('active/', views.ActivePlansView.as_view(), name='active'),
    path('rewards/', views.RewardListView.as_view(), name='rewards'),
    path('rewards/<str:reward_id>/', views.RewardDetailView.as_view(), name='reward-detail'),
    path('purchases/', views.PurchaseHistoryView.as_view(), name='purchases'),
    path('purchase/', views.PurchaseView.as_view(), name='purchase'),
    # Section 4 dashboard endpoint (kept for compatibility).
    path('current/', views.CurrentPlanView.as_view(), name='current'),
]
