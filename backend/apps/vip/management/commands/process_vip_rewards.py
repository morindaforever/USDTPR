"""Manual reward processing (Section 8 §28; gated for conversion §12).

Runs the SAME reward service as Celery Beat — no duplicate calculation
logic (§29). Idempotent: re-running respects existing rewards, target
caps, and purchase status.

Conversion §12: the daily AUTOMATION (Celery Beat) is disabled unless
``REWARD_PAYOUTS_ENABLED=True``; this command remains the operator's
audited manual path — every credit still flows through the wallet service
with full ledger + audit history.

Usage::

    python manage.py process_vip_rewards
    python manage.py process_vip_rewards --cycle-date 2026-09-16
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.vip.reward_service import current_cycle, process_daily_rewards


class Command(BaseCommand):
    help = 'Process VIP rewards for a reward cycle (idempotent, safe to re-run).'

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            '--cycle-date',
            type=str,
            default=None,
            help='ISO date of the reward cycle to process (default: current cycle).',
        )

    def handle(self, *args, **options) -> None:
        raw = options['cycle_date']
        if raw:
            try:
                cycle = date.fromisoformat(raw)
            except ValueError as exc:
                raise CommandError(f'Invalid --cycle-date {raw!r}: use YYYY-MM-DD.') from exc
        else:
            cycle = current_cycle()

        stats = process_daily_rewards(cycle)
        self.stdout.write(self.style.SUCCESS(
            f"Cycle {stats['cycle']}: eligible={stats['eligible']} "
            f"credited={stats['credited']} completed={stats['completed']} "
            f"skipped={stats['skipped']} failed={stats['failed']}"
        ))
