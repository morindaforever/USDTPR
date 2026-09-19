"""Create the standard admin permission groups (Section 12 §65–66, §106).

Usage::

    python manage.py bootstrap_admin_groups
"""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.adminpanel.permissions_config import ADMIN_GROUPS


class Command(BaseCommand):
    help = 'Create the standard admin permission groups (idempotent).'

    def handle(self, *args, **options) -> None:
        for name, description in ADMIN_GROUPS.items():
            group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {name} — {description}'))
            else:
                self.stdout.write(f'Exists: {name}')
        self.stdout.write(self.style.SUCCESS('Admin groups ready.'))
