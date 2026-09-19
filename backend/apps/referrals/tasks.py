"""Celery tasks for the referrals app (Section 9 §45–46).

Commissions are normally paid synchronously by the Section 8 reward engine
right after a reward commits (same worker, one hop, still idempotent). This
task exists for retries and manual re-runs: it is a thin idempotent wrapper
around ``commission_service.process_referral_commission`` — all business
logic lives in the service.
"""

from __future__ import annotations

import logging

from celery import shared_task

from apps.referrals.commission_service import CommissionError

logger = logging.getLogger('referrals.commissions')


@shared_task(
    bind=True,
    name='referrals.process_referral_commission',
    max_retries=3,
    default_retry_delay=30,
    autoretry_for=(Exception,),
    dont_autoretry_for=(CommissionError,),
    retry_backoff=True,
    retry_jitter=True,
)
def process_referral_commission_task(self, reward_id: str):
    """Pay (or re-pay failed) commissions for one credited VIP reward."""
    from apps.referrals.commission_service import process_referral_commission

    outcomes = process_referral_commission(reward_id)
    return [
        {'user': o.user_id, 'level': o.level, 'status': o.status,
         'amount': str(o.amount) if o.amount is not None else None}
        for o in outcomes
    ]
