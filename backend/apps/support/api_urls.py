"""Support API routes (Section 11 §51)."""

from django.urls import path

from . import api_views

app_name = 'support'

urlpatterns = [
    path('conversations/', api_views.SupportConversationListCreateView.as_view(), name='conversations'),
    path(
        'conversations/<str:conversation_id>/',
        api_views.SupportConversationDetailView.as_view(),
        name='conversation-detail',
    ),
    path(
        'conversations/<str:conversation_id>/messages/',
        api_views.SupportMessageCreateView.as_view(),
        name='conversation-messages',
    ),
    path(
        'conversations/<str:conversation_id>/close/',
        api_views.SupportConversationCloseView.as_view(),
        name='conversation-close',
    ),
    path(
        'conversations/<str:conversation_id>/reopen/',
        api_views.SupportConversationReopenView.as_view(),
        name='conversation-reopen',
    ),
]
