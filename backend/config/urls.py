"""Root URL configuration.

All API endpoints live under /api/. App-level URLs are registered by their
respective sections to keep changes scoped.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('apps.accounts.urls')),
    path('api/wallet/', include('apps.wallet.urls')),
    path('api/vip/', include('apps.vip.urls')),
    path('api/referrals/', include('apps.referrals.urls')),
    path('api/deposits/', include('apps.deposits.urls')),
    path('api/admin-panel/', include('apps.deposits.admin_urls')),
    path('api/admin-panel/', include('apps.withdrawals.admin_urls')),
    path('api/admin/', include('apps.adminpanel.urls')),
    path('api/withdrawals/', include('apps.withdrawals.api_urls')),
    path('api/account/', include('apps.accounts.account_urls')),
    path('api/support/', include('apps.support.api_urls')),
    path('api/notifications/', include('apps.notifications.urls')),
    path('api/', include('apps.core.urls')),]
