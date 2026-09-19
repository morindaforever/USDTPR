# Notifications & Transaction History (Section 13)

User-facing notification center and unified transaction history. Both read
exclusively from existing systems — **no new accounting surface**:

```
WalletTransaction (Section 5) = canonical financial ledger → /transactions
Notification (Section 2)      = user-facing event information → /notifications
```

Deposits, withdrawals, VIP, rewards, referral, support, and security events
emit notifications through one centralized, idempotent service; the ledger
remains the single source of financial truth.

## Notification APIs (`/api/notifications/`, auth required)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/notifications/` | Own notifications, newest first. Filters: `?type=REWARD` (validated choice), `?is_read=true|false`, `?page=&page_size=`. Response includes `unread_count` alongside the standard envelope. |
| `GET /api/notifications/unread-count/` | Badge source — `{data: {unread_count: N}}`. Never hardcoded in the UI. |
| `GET /api/notifications/<id>/` | Detail; other users' notifications 404 (no existence leak). |
| `POST /api/notifications/<id>/read/` | Idempotent mark-read: sets `is_read`/`read_at` once; repeat calls return 200 and never clobber `read_at`. |
| `POST /api/notifications/read-all/` | Marks all unread read; returns `{marked, unread_count}`. Repeat call is a 0-marked no-op. |

No delete endpoint: notifications referencing financial history are kept
(§6 — users cannot destroy records that support audit/history).

## Notification types

`DEPOSIT`, `WITHDRAWAL`, `VIP`, `REWARD`, `REFERRAL`, `SUPPORT`,
`SECURITY`, `ANNOUNCEMENT`, `SYSTEM` — controlled `TextChoices`.

## Event integration (idempotent, transaction-safe)

All application code creates notifications via
`apps/notifications/services.py` (`notify`, `notify_event`). Financial
events use **`notify_event`** with a deterministic key
(`reward:<id>:credited`, `withdrawal:<id>:completed`, …) protected by a
partial unique constraint `(user, event_key)` — retries/replays can never
duplicate a notification (§19). Notifications are created **inside** the
caller's `transaction.atomic` block, so a rollback removes the
notification together with the finance change it describes (§18).

Call sites wired: deposits (submitted/approved/rejected), withdrawals
(submitted/approved/rejected/processing/completed/failed), VIP
(activated), rewards (credited/completed), referral commissions (credited),
support (new reply), security (password changed).

## Transaction history (`/api/wallet/transactions/`, auth required)

Existing Section 5 endpoints, extended:

- Filters: `?type=`, `?status=`, `?direction=`, `?date_from=&date_to=`
  (inclusive ISO dates), `?page=&page_size=`.
- **New (§23):** `?search=` — matches `transaction_id` (exact), or
  `description` (contains), or `reference_id` (exact). Parameterized
  ORM queries only; no field injection.
- Detail: `GET /api/wallet/transactions/<transaction_id>/` — public
  `TXN…` id, scoped to the requesting user.

### Security model

Every queryset is filtered by `request.user` at the backend. Another
user's transaction/notification 404s even with a known id — ownership is
never enforced in the frontend alone. Users cannot mutate balances
through any endpoint in this section; the ledger is read-only over the API.

## Frontend

| Route | Page |
| --- | --- |
| `/notifications` | Notification center: All/Unread + type filter chips, mark read per item, Mark all read, pagination, relative timestamps (absolute in tooltip), skeleton/empty/error states. |
| `/transactions` | Unified ledger: search box, type chips, status select, date range, pagination; desktop table + mobile card layout (no horizontal overflow at 320px). |
| `/transactions/:transactionId` | Detail: amount hero, type/direction/balance/status/description/date/reference; contextual cross-link to the owning feature page (deposit → `/deposit`, withdrawal → `/withdraw`, VIP → `/vip`, commission → `/team`); demo-environment disclaimer. |

Dashboard (Section 4) gained `RecentTransactions` and
`RecentNotifications` cards (latest 5 each, "View All" links to
`/transactions` and `/notifications`). The header bell shows the live
unread count from `unread-count/` and refreshes on navigation.

## Testing

```bash
cd backend
python manage.py test apps.notifications --noinput          # Section 13 suite
python manage.py test apps.notifications apps.deposits apps.withdrawals \
    apps.vip apps.referrals apps.support apps.accounts apps.wallet --noinput
```

Coverage (26 tests): auth required, list/newest-first, user isolation,
type + `is_read` filters, invalid filter 400, pagination, unread count,
detail, mark-read idempotency (timestamp preserved), mark-read of another
user's notification 404, read-all + repeat no-op, `notify_event`
duplicate protection (same key → same row; same key across users OK),
ledger→notification event integration with full replay (nothing
duplicates), rollback removes the notification with the ledger row
(§18), transaction search by description/reference/transaction id,
user-scoped search, SQL-injection-probe safety, date-range filter.

## Known limitations

- No WebSockets (§30): the badge refreshes on mount/navigation and via a
  slow interval only.
- No notification delete endpoint, by design.
- Real-time push, email/push channels, and admin announcement composition
  beyond the Section 12 broadcast remain future work.
