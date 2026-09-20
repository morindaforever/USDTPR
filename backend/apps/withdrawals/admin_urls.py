"""Admin withdrawal-management API routes (Section 10 §48).

Mounted at ``/api/admin-panel/`` next to the deposits admin routes.
``IsAdminUser`` is enforced by every view's ``permission_classes`` — route
protection alone is never trusted (§54).
"""

from django.urls import path

from . import views

app_name = 'admin-withdrawals'

urlpatterns = [
    path('withdrawals/', views.AdminWithdrawalListView.as_view(), name='list'),
    path('withdrawals/<str:withdrawal_id>/', views.AdminWithdrawalDetailView.as_view(), name='detail'),
    path('withdrawals/<str:withdrawal_id>/qr/', views.AdminWithdrawalQRView.as_view(), name='qr'),
    path('withdrawals/<str:withdrawal_id>/approve/', views.AdminApproveView.as_view(), name='approve'),
    path('withdrawals/<str:withdrawal_id>/reject/', views.AdminRejectView.as_view(), name='reject'),
    path('withdrawals/<str:withdrawal_id>/processing/', views.AdminProcessingView.as_view(), name='processing'),
    path('withdrawals/<str:withdrawal_id>/complete/', views.AdminCompleteView.as_view(), name='complete'),
    path('withdrawals/<str:withdrawal_id>/fail/', views.AdminFailView.as_view(), name='fail'),
]
