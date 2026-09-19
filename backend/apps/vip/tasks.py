"""Celery tasks for the VIP app (Section 8).

The task is a thin wrapper — ALL business logic lives in
``reward_service.process_daily_rewards``. Retries are safe: the reward
engine is idempotent per (purchase, cycle), so a re-run after a worker
crash or broker retry can never credit twice (§17, §27).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task
from celery.schedules import crontab
from django.conf import settings

from .reward_service import current_cycle, process_daily_rewards

logger = logging.getLogger('vip.rewards')


class RewardAutomationDisabled(Exception):
    """Raised when the scheduled reward run fires while the automation gate is off."""


@shared_task(name='vip.process_daily_vip_rewards', bind=True, max_retries=3, default_retry_delay=60)
def process_daily_vip_rewards(self, cycle_date: str | None = None) -> dict:
    """Daily VIP reward run (scheduled via Celery Beat).

    Conversion §12: the scheduled AUTOMATION is disabled unless the operator
    has explicitly set ``REWARD_PAYOUTS_ENABLED=True`` — the reward scheme
    must not run for public users without legal review. Staff can still run
    the audited manual management command, which bypasses this gate
    deliberately (it is operator-initiated and audit-logged).

    ``cycle_date`` is an optional ISO date override — used by tests and the
    management command; the scheduled run always uses the current cycle.
    """
    if not getattr(settings, 'REWARD_PAYOUTS_ENABLED', False):
        logger.warning(
            'Daily reward automation skipped: REWARD_PAYOUTS_ENABLED is False. '
            'No rewards were credited by automation.'
        )
        return {'cycle': cycle_date or current_cycle().isoformat(), 'eligible': 0,
                'credited': 0, 'completed': 0, 'skipped': 0, 'failed': 0,
                'automation_disabled': True}
    cycle = date.fromisoformat(cycle_date) if cycle_date else current_cycle()
    try:
        return process_daily_rewards(cycle)
    except Exception as exc:  # pragma: no cover - Celery retry path
        logger.error('Daily reward run failed cycle=%s: %s', cycle.isoformat(), exc)
        raise self.retry(exc=exc)


def beat_schedule() -> dict:
    """Beat entry for the daily reward run.

    Runs at 00:15 in the CELERY_TIMEZONE (project timezone — §27 forbids a
    hard-coded UTC assumption), right after local midnight so the
    calendar-day cycle (§9) is unambiguous. Duplicate ticks / retries are
    harmless: the engine is idempotent per (purchase, cycle).
    """
    return {
        'process-daily-vip-rewards': {
            'task': 'vip.process_daily_vip_rewards',
            'schedule': crontab(hour=0, minute=15),
            'options': {'expires': 3600},
        },
    }
