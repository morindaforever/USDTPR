"""Admin panel API routes (Section 12 §64).

Mounted at ``/api/admin/`` from ``config/urls.py``. Every view enforces
``IsAuthenticated + IsAdminUser`` (plus per-action group gates) in its own
permission_classes — route protection alone is never trusted (§3, §70).
"""

from django.urls import path

from . import dashboard_views, finance_views, ops_views, user_views

app_name = 'adminpanel'

urlpatterns = [
    # Dashboard (§7–9)
    path('dashboard/', dashboard_views.AdminDashboardView.as_view(), name='dashboard'),
    # Users (§10–17)
    path('users/', user_views.AdminUserListCreateView.as_view(), name='users'),
    path('users/<str:user_id>/', user_views.AdminUserDetailView.as_view(), name='user-detail'),
    path('users/<str:user_id>/status/', user_views.AdminUserStatusView.as_view(), name='user-status'),
    path('users/<str:user_id>/history/', user_views.AdminUserHistoryView.as_view(), name='user-history'),
    # Deposits (§18–22)
    path('deposits/', finance_views.AdminDepositListView.as_view(), name='deposits'),
    path('deposits/<str:deposit_id>/', finance_views.AdminDepositDetailView.as_view(), name='deposit-detail'),
    path('deposits/<str:deposit_id>/approve/', finance_views.AdminDepositActionView.as_view(), {'action': 'approve'}, name='deposit-approve'),
    path('deposits/<str:deposit_id>/reject/', finance_views.AdminDepositActionView.as_view(), {'action': 'reject'}, name='deposit-reject'),
    # Withdrawals (§24–29)
    path('withdrawals/', finance_views.AdminWithdrawalListView.as_view(), name='withdrawals'),
    path('withdrawals/<str:withdrawal_id>/', finance_views.AdminWithdrawalDetailView.as_view(), name='withdrawal-detail'),
    path('withdrawals/<str:withdrawal_id>/approve/', finance_views.AdminWithdrawalActionView.as_view(), {'action': 'approve'}, name='withdrawal-approve'),
    path('withdrawals/<str:withdrawal_id>/reject/', finance_views.AdminWithdrawalActionView.as_view(), {'action': 'reject'}, name='withdrawal-reject'),
    path('withdrawals/<str:withdrawal_id>/processing/', finance_views.AdminWithdrawalActionView.as_view(), {'action': 'processing'}, name='withdrawal-processing'),
    path('withdrawals/<str:withdrawal_id>/complete/', finance_views.AdminWithdrawalActionView.as_view(), {'action': 'complete'}, name='withdrawal-complete'),
    path('withdrawals/<str:withdrawal_id>/fail/', finance_views.AdminWithdrawalActionView.as_view(), {'action': 'fail'}, name='withdrawal-fail'),
    # VIP plans & purchases (§30–35)
    path('vip-plans/', finance_views.AdminVIPPlanListCreateView.as_view(), name='vip-plans'),
    path('vip-plans/<int:pk>/', finance_views.AdminVIPPlanDetailView.as_view(), name='vip-plan-detail'),
    path('vip-purchases/', finance_views.AdminVIPPurchaseListView.as_view(), name='vip-purchases'),
    # Rewards (§36–39)
    path('rewards/', finance_views.AdminRewardListView.as_view(), name='rewards'),
    path('rewards/process/', finance_views.AdminRewardProcessView.as_view(), name='reward-process'),
    path('rewards/<str:reward_id>/retry/', finance_views.AdminRewardRetryView.as_view(), name='reward-retry'),
    # Wallet transactions (§49–50)
    path('transactions/', finance_views.AdminTransactionListView.as_view(), name='transactions'),
    # Referrals & commissions (§40–43)
    path('referrals/', ops_views.AdminReferralListView.as_view(), name='referrals'),
    path('commissions/', ops_views.AdminCommissionListView.as_view(), name='commissions'),
    # Support (§44–48)
    path('support/', ops_views.AdminSupportListCreateView.as_view(), name='support'),
    path('support/<str:conversation_id>/', ops_views.AdminSupportDetailView.as_view(), name='support-detail'),
    path('support/<str:conversation_id>/messages/', ops_views.AdminSupportReplyView.as_view(), name='support-reply'),
    path('support/<str:conversation_id>/status/', ops_views.AdminSupportStatusView.as_view(), name='support-status'),
    # Notifications (§52–53)
    path('notifications/', ops_views.AdminNotificationListView.as_view(), name='notifications'),
    path('notifications/broadcast/', ops_views.AdminBroadcastView.as_view(), name='broadcast'),
    # Audit logs (§54–55)
    path('audit-logs/', ops_views.AdminAuditLogListView.as_view(), name='audit-logs'),
    # Settings (§56–63)
    path('settings/', ops_views.AdminSettingsListEditView.as_view(), name='settings'),
]
