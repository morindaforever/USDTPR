"""Notification API routes (Section 13 §6)."""

from django.urls import path

from . import api_views

app_name = 'notifications'

urlpatterns = [
    path('', api_views.NotificationListView.as_view(), name='list'),
    path('unread-count/', api_views.UnreadCountView.as_view(), name='unread-count'),
    path('read-all/', api_views.ReadAllView.as_view(), name='read-all'),
    path('<int:notification_id>/', api_views.NotificationDetailView.as_view(), name='detail'),
    path('<int:notification_id>/read/', api_views.NotificationReadView.as_view(), name='read'),
]
