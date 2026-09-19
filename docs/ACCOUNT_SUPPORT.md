# Account & Support System (Section 11)

User-facing account management and support conversations. Built on the
Section 3 authentication services, Section 2 support models, and the existing
notification/audit infrastructure — no duplicate systems.

## Account APIs (`/api/account/`, auth required)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/account/me/` | Safe profile (`user_id`, full_name, email, phone, referral_code, account_status) — no password/token fields ever serialize |
| `PATCH /api/account/profile/` | Update `full_name` and/or `phone` (§7). All other payload keys (user_id, email, account_status, is_staff, referral_code, …) are ignored by the serializer — privilege escalation is structurally impossible (§77) |
| `POST /api/account/change-password/` | Validates current password + confirmation + Django password validators; on success **blacklists every outstanding refresh token** so old sessions cannot persist (§16), then writes a `PASSWORD_CHANGED` audit row with no password material (§56) |
| `GET /api/account/activity/` | Curated, safe activity feed (logins, profile updates, deposits, withdrawals, VIP purchases, rewards) — raw `AuditLog`/`LoginActivity` internals (IPs, user agents, target ids) are never exposed (§19–§20) |

Email is deliberately read-only: no secure email-change flow exists in the
auth architecture, so none is exposed (§7). Password reset reuses the
existing `/api/auth/forgot-password/` + `/reset-password/` flow (§17).

## Support APIs (`/api/support/`, auth required)

| Endpoint | Purpose |
| --- | --- |
| `GET /api/support/conversations/?status=…&page=…` | Paginated list (EnvelopePagination), server-side status filter (`OPEN`, `IN_PROGRESS`, `RESOLVED`, `CLOSED`), last-message preview (§28, §40–41) |
| `POST /api/support/conversations/` | Creates conversation + first message atomically; subject/message required, ≤200/≤5000 chars (§30–31) |
| `GET /api/support/conversations/<id>/` | Owner-only detail with capped message thread (200 msgs); foreign ids get the same 404 as missing ones — IDOR-safe (§34, §53) |
| `POST /api/support/conversations/<id>/messages/` | Append message; user replies flip status to `IN_PROGRESS`; closed threads reject with 409 (§35–37) |
| `POST /api/support/conversations/<id>/close/` | Owner-only; idempotent — double close returns 200 with "already closed" (§38) |
| `POST /api/support/conversations/<id>/reopen/` | Owner-only; only CLOSED threads can reopen (§39) |

### Statuses

`OPEN → IN_PROGRESS` (user reply / reopen) `→ RESOLVED` (admin, later
section) `→ CLOSED` (user). Messages are plain text end-to-end: React
escapes by default and `javascript:`/`data:`/`vbscript:` URL schemes are
rejected at the service layer (§33, §75).

### Notifications & audit

Every staff reply creates exactly one `SUPPORT` notification for the owner
(§42). Conversation create/close/reopen and message sends write audit rows
without message content (§57).

### Rate limits (§47)

Fixed-window counters in the shared Redis cache: 5 new conversations/hour
and 30 messages/hour per user. Exceeding them returns HTTP 429 with the
standard envelope; windows self-expire so legitimate users are never
permanently blocked.

## Frontend routes

| Route | Access | Content |
| --- | --- | --- |
| `/account` | auth | Profile card + edit, referral code/link copy, curated activity, links to wallet/withdraw/VIP history, security (change/forgot password), support links, logout |
| `/account/change-password` | auth | Existing Section 3 change-password page |
| `/support` | auth | Filter tabs (All/Open/Waiting/Resolved/Closed), paginated conversation list, New Conversation modal with subject presets |
| `/support/:conversationId` | auth | Thread (oldest → newest), reply composer, close/reopen, manual refresh |
| `/help` | public | Categorized FAQ accordions from `src/data/faq.ts` + demo/test notice + link into `/support` |

## Testing

```bash
cd backend && python manage.py test apps.support apps.accounts
```

41 Section 11 tests cover: profile update + protected-field rejection,
phone validation/duplicates, password change (wrong current, weak,
mismatch, same-as-old), refresh-token blacklisting, no-password-material
audit, activity isolation, conversation lifecycle, closed-thread guards,
idempotent close, IDOR isolation, XSS payload storage, link-scheme
rejection, both rate limits, notification behavior, and audit rows.
