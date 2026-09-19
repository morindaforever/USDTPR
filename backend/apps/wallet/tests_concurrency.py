"""Concurrency tests for the wallet service (Section 5, requirement 41).

Uses real threads against PostgreSQL so ``select_for_update`` row locking is
exercised end to end: two simultaneous debits of the same funds must result
in exactly one success — never a negative balance, never a double spend.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier

from django.db import close_old_connections, connection
from django.test import TransactionTestCase

from apps.accounts.models import User
from apps.wallet.models import Wallet, WalletTransaction
from apps.wallet.services import InsufficientBalanceError, credit, debit, lock

BT = WalletTransaction.BalanceType
TT = WalletTransaction.TransactionType


class ConcurrencyTests(TransactionTestCase):
    def setUp(self) -> None:
        self.user = User.objects.create_user(
            email='concurrency@example.com', password='S3curePass!', phone='+15550300001',
            full_name='Concurrency User',
        )
        Wallet.objects.create(user=self.user)
        credit(user=self.user, amount='100', balance_type=BT.WITHDRAWABLE,
               transaction_type=TT.ADJUSTMENT, idempotency_key='conc-seed')

    def _run_parallel(self, fn, workers: int):
        barrier = Barrier(workers)

        def runner(index: int):
            close_old_connections()
            barrier.wait()  # maximize contention
            try:
                return fn(index), None
            except Exception as exc:  # noqa: BLE001 - outcome collected below
                return None, exc
            finally:
                # Drop this thread's session immediately (CONN_MAX_AGE would
                # otherwise keep it open and block test-DB teardown).
                connection.close()

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(runner, range(workers)))
        return results

    def test_parallel_debits_cannot_double_spend(self) -> None:
        """Two concurrent 80-USDT debits against a 100-USDT balance:
        exactly one succeeds, balance lands at 20, never negative."""

        def attempt(index: int):
            return debit(
                user=self.user, amount='80', balance_type=BT.WITHDRAWABLE,
                transaction_type=TT.WITHDRAWAL,
                description=f'parallel attempt {index}',
                idempotency_key=f'conc-debit-{index}',
            )

        results = self._run_parallel(attempt, workers=2)
        succeeded = [r for r, err in results if err is None]
        failed = [err for _, err in results if err is not None]

        self.assertEqual(len(succeeded), 1, f'expected exactly one success, got {len(succeeded)}')
        self.assertEqual(len(failed), 1)
        self.assertIsInstance(failed[0], InsufficientBalanceError)

        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.withdrawable_balance, Decimal('20.00000000'))
        self.assertEqual(wallet.total_balance, Decimal('20.00000000'))
        completed_debits = WalletTransaction.objects.filter(
            user=self.user, transaction_type=TT.WITHDRAWAL, status=WalletTransaction.Status.COMPLETED,
        ).count()
        self.assertEqual(completed_debits, 1)

    def test_parallel_locks_cannot_overcommit(self) -> None:
        """Three concurrent 50-USDT locks against a 100-USDT withdrawable
        bucket: exactly two succeed (100 committed), locked totals 100."""

        def attempt(index: int):
            return lock(user=self.user, amount='50', reference_type='withdrawal',
                        reference_id=f'WDR-CONC-{index}', idempotency_key=f'conc-lock-{index}')

        results = self._run_parallel(attempt, workers=3)
        succeeded = [r for r, err in results if err is None]
        self.assertEqual(len(succeeded), 2)

        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.locked_balance, Decimal('100.00000000'))
        self.assertEqual(wallet.withdrawable_balance, Decimal('0.00000000'))
        self.assertEqual(wallet.total_balance, Decimal('100.00000000'))

    def test_parallel_idempotent_credits_credit_once(self) -> None:
        """Two workers racing the SAME idempotency key must yield one credit."""
        from apps.wallet.services import DuplicateTransactionError

        def attempt(index: int):
            return credit(user=self.user, amount='50', balance_type=BT.DEPOSIT,
                          transaction_type=TT.DEPOSIT, idempotency_key='race-key')

        results = self._run_parallel(attempt, workers=2)
        succeeded = [r for r, err in results if err is None]
        duplicate_rejected = any(isinstance(err, DuplicateTransactionError) for _, err in results)

        wallet = Wallet.objects.get(user=self.user)
        credited = wallet.deposit_balance
        # Exactly one 50 credit landed: either one worker succeeded after the
        # other's committed row was visible, or the unique constraint blocked
        # the loser. Never 100.
        self.assertEqual(credited, Decimal('50.00000000'))
        self.assertTrue(len(succeeded) == 1 or duplicate_rejected,
                        f'succeeded={len(succeeded)} duplicate_rejected={duplicate_rejected}')
