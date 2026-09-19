"""Attempt on-chain verification of pending deposits (conversion §4).

Operator tool for the enabled-provider future; with
``CHAIN_VERIFICATION_ENABLED=False`` it reports that verification is
disabled and changes nothing — admin review remains the approval path.

Usage::

    python manage.py verify_deposits                 # all PENDING with a hash
    python manage.py verify_deposits --deposit DEP00000001
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.core.models import AuditLog
from apps.deposits.models import Deposit
from apps.deposits.services import approve_deposit
from apps.integrations.base import NoProviderConfiguredError, TransactionNotVerified, VerificationError
from apps.integrations.chain import verify_deposit


class Command(BaseCommand):
    help = (
        'Run independent on-chain verification over pending deposits and '
        'auto-approve only those that fully pass the verification checklist. '
        'Requires CHAIN_VERIFICATION_ENABLED and a configured chain provider.'
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument('--deposit', type=str, default=None,
                            help='Verify a single deposit by its public ID.')

    def handle(self, *args, **options) -> None:
        target = options['deposit']
        if target:
            deposits = Deposit.objects.filter(deposit_id=target, status=Deposit.Status.PENDING)
            if not deposits.exists():
                raise CommandError(f'No pending deposit found with id {target!r}.')
        else:
            deposits = Deposit.objects.filter(
                status=Deposit.Status.PENDING,
            ).exclude(tx_hash='').order_by('created_at')

        if not deposits:
            self.stdout.write('No pending deposits with a transaction hash to verify.')
            return

        passed = failed = 0
        for deposit in deposits:
            try:
                result = verify_deposit(deposit)
            except NoProviderConfiguredError as exc:
                raise CommandError(str(exc)) from exc
            except (TransactionNotVerified, VerificationError) as exc:
                failed += 1
                deposit.verification_note = str(exc)[:255]
                deposit.save(update_fields=['verification_note', 'updated_at'])
                self.stdout.write(self.style.WARNING(
                    f'{deposit.deposit_id}: NOT VERIFIED — {exc}'
                ))
                continue

            deposit.verified_at = timezone.now()
            deposit.verification_note = (
                f'On-chain verified: {result.confirmations} confirmations, '
                f'amount {result.amount} {deposit.asset}.'
            )[:255]
            approve_deposit(
                deposit=deposit,
                admin_user=None,
                note='Auto-approved by on-chain verification.',
            )
            passed += 1
            self.stdout.write(self.style.SUCCESS(f'{deposit.deposit_id}: verified + credited.'))

        AuditLog.objects.create(
            actor_user=None,
            action=AuditLog.Action.APPROVE,
            target_type='deposit_verification_run',
            target_id='verify_deposits',
            description=f'On-chain verification run: {passed} credited, {failed} not verified.',
        )
        self.stdout.write(self.style.SUCCESS(f'Done. verified={passed} rejected_for_review={failed}'))
