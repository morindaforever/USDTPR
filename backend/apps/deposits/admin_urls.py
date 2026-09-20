"""Admin deposit-management API routes (is_staff enforced by permissions)."""

from django.urls import path

from . import admin_views

app_name = 'admin-deposits'


class ApproveView(admin_views.AdminDepositActionView):
    def post(self, request, deposit_id: str):  # noqa: D102 - action fixed
        return super().post(request, deposit_id, 'approve')


class RejectView(admin_views.AdminDepositActionView):
    def post(self, request, deposit_id: str):  # noqa: D102 - action fixed
        return super().post(request, deposit_id, 'reject')


urlpatterns = [
    path('deposits/', admin_views.AdminDepositListView.as_view(), name='deposit-list'),
    path('deposits/<str:deposit_id>/', admin_views.AdminDepositDetailView.as_view(), name='deposit-detail'),
    path('deposits/<str:deposit_id>/approve/', ApproveView.as_view(), name='deposit-approve'),
    path('deposits/<str:deposit_id>/reject/', RejectView.as_view(), name='deposit-reject'),
    path('deposits/<str:deposit_id>/note/', admin_views.AdminDepositNoteView.as_view(), name='deposit-note'),
    path('deposits/<str:deposit_id>/screenshot/', admin_views.AdminDepositScreenshotView.as_view(), name='deposit-screenshot'),
    path('deposit-addresses/', admin_views.AdminDepositAddressListCreateView.as_view(), name='address-list'),
    path('deposit-addresses/<int:pk>/', admin_views.AdminDepositAddressDetailView.as_view(), name='address-detail'),
    path('networks/', admin_views.AdminNetworkListView.as_view(), name='network-list'),
    path('networks/<int:pk>/', admin_views.AdminNetworkListView.as_view(), name='network-detail'),
]
