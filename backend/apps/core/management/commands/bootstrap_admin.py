import os

from django.core.management.base import BaseCommand, CommandError
from apps.accounts.models import User


class Command(BaseCommand):
    help = "Create or promote the production admin account."

    def handle(self, *args, **options):
        email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
        phone = os.getenv("BOOTSTRAP_ADMIN_PHONE", "").strip()

        if not email or not password:
            self.stdout.write(
                self.style.WARNING(
                    "Bootstrap admin variables are not configured. Skipping."
                )
            )
            return

        user = User.objects.filter(email__iexact=email).first()

        if user:
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.account_status = User.AccountStatus.ACTIVE

            # Set the password only when explicitly provided.
            user.set_password(password)
            user.save()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Existing account promoted to admin: {user.email}"
                )
            )
            return

        if not phone:
            raise CommandError(
                "BOOTSTRAP_ADMIN_PHONE is required when creating a new admin."
            )

        user = User.objects.create_superuser(
            email=email,
            password=password,
            phone=phone,
            full_name="NexusUSDT Admin",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Admin account created: {user.email}"
            )
        )
