# Wallet & Balance Ledger System (Section 5)

The internal accounting foundation. Every financial module (deposits,
withdrawals, VIP, referrals, admin adjustments) MUST move money through
`backend/apps/wallet/services/` — direct writes to `Wallet` columns are
forbidden outside the service.

## Architecture

```text
Business Operation (deposit approval, reward job, admin adjustment, …)
       ↓
Wallet Service  (apps/wallet/services/wallet_service.py)
       ↓  validate amount / balance type / account state
Database Transaction  (transaction.atomic)
       ↓  lock wallet row  (SELECT … FOR UPDATE)
       ↓  idempotency check (same key ⇒ return existing result)
       ↓  insufficient-balance check
       ↓  create ledger row(s)   (WalletTransaction)
       ↓  update wallet bucket(s) + recompute total
       ↓
Commit  (or ROLLBACK everything on any failure)
```

The ledger and the wallet are always consistent: both are written inside one
database transaction while holding the wallet row lock. A crash or error at
any point rolls back the whole operation — "ledger says +50, wallet says +0"
is structurally impossible.

## Balance types & accounting policy

| Bucket | Meaning | Mutations |
| --- | --- | --- |
| `deposit_balance` | Funds credited from approved deposits | service credit/debit/transfer |
| `withdrawable_balance` | Funds eligible for withdrawal requests | service credit/debit/lock/transfer |
| `bonus_balance` | Funds from rewards/bonuses | service credit/debit/transfer |
| `locked_balance` | Funds reserved for an in-flight operation | `lock()` / `release_lock()` / `finalize_locked()` |
| `pending_balance` | Funds tentatively associated with pending ops | service operations (future modules) |
| `total_balance` | **Derived** display aggregate | recomputed by the service, never written directly |

**Policy: `total = deposit + withdrawable + bonus + locked + pending`.**
Total is NOT assumed to equal `deposit + withdrawable` — bonus, locked, and
pending also represent holdings. Because the service recomputes total from
the buckets after every operation, the invariant cannot drift; the
reconciliation utility verifies it anyway.

**Only COMPLETED ledger rows affect balances.** PENDING rows are records of
intent (created by future modules for pending withdrawals etc.) with zero
balance effect. REVERSED/FAILED rows are historical.

## Ledger rows (WalletTransaction)

Every row answers: **who** (user FK), **what** (transaction_type), **how
much** (amount, Decimal(24,8)), **direction** (CREDIT/DEBIT), **which
balance** (balance_type), **why** (description), **when** (created_at),
**which business object** (reference_type + reference_id, e.g.
`deposit`/`DEP000123`), plus a unique optional `idempotency_key`.

Transaction types: `DEPOSIT`, `WITHDRAWAL`, `VIP_PURCHASE`, `VIP_REWARD`,
`REFERRAL_COMMISSION`, `WELCOME_BONUS`, `REFUND`, `ADJUSTMENT`, and internal
movement types `LOCK`, `RELEASE`, `TRANSFER`.

Bucket movements (lock/release/transfer) produce **one ledger row per
affected bucket** (e.g. lock = DEBIT withdrawable + CREDIT locked) so every
balance change has its own audit entry.

## Service API (`apps.wallet.services`)

| Operation | Purpose |
| --- | --- |
| `credit(user, amount, balance_type, transaction_type, …, idempotency_key=…)` | Add funds to a bucket |
| `debit(user, amount, balance_type, …, idempotency_key=…)` | Remove funds; rejects on shortfall |
| `lock(user, amount, …)` | withdrawable → locked (withdrawal reservation) |
| `release_lock(user, amount, …)` | locked → withdrawable (request rejected) |
| `finalize_locked(user, amount, …)` | locked → paid out (withdrawal completed) |
| `transfer_between_balances(user, amount, from, to, …)` | Move between buckets |
| `admin_adjust(user, amount, balance_type, direction, reason, actor_user, …)` | Manual adjustment + AuditLog entry |
| `reverse_transaction(ledger, reason, …)` | Post opposite row, mark original REVERSED |
| `get_wallet_summary(user)` | Read-only bucket snapshot |
| `get_wallet(user)` / `ensure_wallet(user)` | Fetch / repair (explicit only) |
| `reconcile_wallet(user)` | Report wallet-vs-ledger discrepancies (never auto-fixes) |

Amounts accept `Decimal`/`str`/`int` — **floats are rejected** by
`normalize_amount` so binary floating-point error can never enter accounts.
All values are quantized to 8 decimal places.

### Error types
`WalletNotFoundError`, `InvalidAmountError`, `InvalidBalanceTypeError`,
`InsufficientBalanceError`, `DuplicateTransactionError`,
`InvalidTransactionError` — all subclasses of `WalletError`. API views map
them to safe `{success, message, errors}` envelopes; stack traces never
reach users.

## Idempotency

- Supply `idempotency_key` on any operation. If a COMPLETED row with that
  key already exists, the original transaction is returned and **no money
  moves again**.
- Multi-leg operations (lock/release/transfer) suffix the second leg's key
  with `:c`.
- Race fallback: the DB unique constraint on `idempotency_key` raises
  `DuplicateTransactionError` if two workers race the same key before either
  commits — verified by a dedicated parallel test.
- Note: a PENDING row holding the key also blocks re-use (unique constraint)
  until its module completes or deletes it.

## Concurrency protection

Every mutating operation locks the wallet row with
`select_for_update()` inside `transaction.atomic()`. Two concurrent debits
serialize on the row lock; the second sees the post-first balance and is
rejected if short. Tested with real threads against PostgreSQL
(`apps/wallet/tests_concurrency.py`): parallel 80-USDT debits against a
100-USDT balance yield exactly one success and a 20-USDT remainder.

## Reconciliation

`reconcile_wallet(user)` compares each wallet bucket against the
direction-aware sum of COMPLETED ledger rows, checks the derived-total
invariant, duplicate idempotency keys, and structurally invalid rows. It
**reports only** — discrepancies are for human investigation, never silent
auto-fixing. CLI: `python manage.py reconcile_wallets [--user USR…] [--strict]`.

## API endpoints (all `IsAuthenticated`, user from token only)

| Endpoint | Description |
| --- | --- |
| `GET /api/wallet/summary/` | Own wallet buckets (Decimal → strings) |
| `GET /api/wallet/transactions/` | Own ledger, paginated (20/page, max 100) with `type`, `status`, `direction`, `date_from`, `date_to`, `page`, `page_size` filters |
| `GET /api/wallet/transactions/<transaction_id>/` | Own transaction detail (other users' TXNs 404) |

There are deliberately **no** user-facing `POST /credit|/debit|/adjust`
endpoints; mutation services are internal. Cross-user access is
structurally impossible — querysets are always scoped to `request.user`.

Response envelopes:

```json
{"success": true, "message": "OK", "data": {…}}
{"success": true, "message": "OK", "data": […], "pagination": {"page": 1, "page_size": 20, "count": 34, "pages": 2}}
```

## Future admin adjustments (prepared, not exposed)

`admin_adjust()` exists for the future admin module: it writes the
ADJUSTMENT ledger row **and** an `AuditLog` entry (actor, reason). Admins
can never silently set `wallet.total_balance = X`.

## Wallet creation

Registration creates the wallet atomically with the user (Section 3).
One user ↔ one wallet is DB-enforced. `ensure_wallet()` is the explicit
repair mechanism for missing wallets — request paths never auto-create.
