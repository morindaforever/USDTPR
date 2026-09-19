"""Cross-cutting Celery tasks.

Section-scoped background jobs (mining/rewards, notifications) are added by
their sections as `tasks.py` modules inside each app.
"""

from celery import shared_task
from django.utils import timezone


@shared_task(name='test_celery_task')
def test_celery_task() -> dict:
    """Smoke-test task proving the broker round-trip works end to end."""
    return {
        'success': True,
        'message': 'Celery is working!',
        'executed_at': timezone.now().isoformat(),
    }
