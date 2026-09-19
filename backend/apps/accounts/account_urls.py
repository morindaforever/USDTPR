"""Account API routes (Section 11 §50)."""

from django.urls import path

from . import account_views

app_name = 'account'

urlpatterns = [
    path('me/', account_views.AccountMeView.as_view(), name='me'),
    path('profile/', account_views.ProfileView.as_view(), name='profile'),
    path('change-password/', account_views.ChangePasswordView.as_view(), name='change-password'),
    path('activity/', account_views.AccountActivityView.as_view(), name='activity'),
]
