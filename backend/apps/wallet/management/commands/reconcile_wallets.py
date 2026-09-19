"""Reconcile wallets against the ledger and report discrepancies.

Reports only — never auto-fixes. Run periodically (or before audits):

    python manage.py reconcile_wallets            # all users
    python manage.py reconcile_wallets --user USR000001
    python manage.py reconcile_wallets --strict   # non-zero exit on issues
"""

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.wallet.models import Wallet
from apps.wallet.services import reconcile_wallet

try:
    from apps.withdrawals.reconciliation import reconcile_user_withdrawals
except ImportError:  # withdrawals app not installed
    reconcile_user_withdrawals = None


class Command(BaseCommand):
    help = 'Detect wallet/ledger inconsistencies and report them for investigation.'

    def add_arguments(self, parser):
        parser.add_argument('--user', dest='user_id', help='Reconcile a single user by public user ID.')
        parser.add_argument('--strict', action='store_true', help='Exit non-zero when issues are found.')

    def handle(self, *args, **options) -> None:
        user_id = options.get('user_id')
        if user_id:
            users = User.objects.filter(user_id=user_id)
            if not users.exists():
                self.stdout.write(self.style.ERROR(f'No user {user_id}'))
                return
        else:
            users = User.objects.filter(wallet__isnull=False)

        problem_users = 0
        checked = 0
        for user in users.iterator():
            checked += 1
            report = reconcile_wallet(user)
            # §80: withdrawal invariants are part of the same reconciliation
            # report — no separate accounting system.
            if reconcile_user_withdrawals is not None:
                report['issues'].extend(reconcile_user_withdrawals(user))
                report['ok'] = not report['issues']
            if report['ok']:
                self.stdout.write(f"  {report['user_id']}: OK")
            else:
                problem_users += 1
                self.stdout.write(self.style.ERROR(f"  {report['user_id']}: {len(report['issues'])} issue(s)"))
                for issue in report['issues']:
                    self.stdout.write(self.style.ERROR(f'    - {issue}'))

        self.stdout.write(f'\nChecked {checked} wallet(s); {problem_users} with issues.')
        if options.get('strict') and problem_users:
            self.stdout.write(self.style.ERROR('STRICT: failing due to discrepancies.'))
            raise SystemExit(1)
