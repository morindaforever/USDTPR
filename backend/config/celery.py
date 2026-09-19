"""Celery application for the USDT platform.

Imported by `config/__init__.py` so Django's runtime always has the app
registered, and so `@shared_task` decorators in apps resolve correctly.
"""

import os

from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.dev')

app = Celery('usdt_platform')

# Read configuration from Django settings with the CELERY_ namespace,
# e.g. CELERY_BROKER_URL -> broker_url. Beat schedule also comes from
# settings (CELERY_BEAT_SCHEDULE) — app code must not be imported here
# because this module loads before Django's app registry is ready.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Discover tasks in each installed app's tasks.py.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:
    """Print the request context — useful when debugging the worker."""
    print(f'Request: {self.request!r}')
