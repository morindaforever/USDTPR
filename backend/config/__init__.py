"""Project config package — imports the Celery app for registration."""

from .celery import app as celery_app

__all__ = ('celery_app',)
