# Security Documentation

Security architecture, rules, and the production checklist for the NexusUSDT
platform. This document describes what IS implemented — it does not claim
production certification, and real-funds activation is gated on the
integration and compliance checklist below.

## Security architecture

```
React SPA ──JWT (in-memory)──▶ Django REST Framework
   │                              │
   │ HttpOnly refresh cookie      ├─ IsAuthenticated (user surface)
   └─ CSRF token (double submit)  ├─ IsAdminUser + GroupPermission (admin surface)
                                  └─ wallet service = ONLY balance mutation path
```

- **Frontend never decides security.** Route guards and hidden buttons are
  UX only; every API enforces authentication, ownership, and permissions
  server-side.
- **Identity**: SimpleJWT access tokens (15 min) kept in memory only — never
  `localStorage`/`sessionStorage`. Rotation with blacklist on refresh; the
  refresh token is an HttpOnly cookie. Django password hashing only.
- **Account statuses** (`ACTIVE`/`SUSPENDED`/`BANNED`) are enforced at the
  service layer via `apps.accounts.services.ensure_active` — deposits, VIP
  purchases, withdrawals, and support messages are rejected server-side for
  non-active accounts, and login itself is blocked.

## Financial integrity rules

1. **Ledger-first.** `WalletTransaction` is the canonical record; wallet
   buckets are derived state updated inside the same `transaction.atomic()`
   block.
2. **Single mutation path.** All balance changes go through
   `apps/wallet/services/wallet_service.py` (`credit`, `debit`, `lock`,
   `release_lock`, `finalize_locked`, `admin_adjust`). Views and other
   services may never write `*_balance` columns directly — a static test
   (`apps.core.tests_security`) fails the build if that pattern appears.
3. **Idempotency.** Every retry-sensitive operation takes a deterministic
   idempotency/event key: wallet ops (`idempotency_key`), rewards
   (`reward:<id>:credited`), notifications (`event_key` unique per user),
   withdrawal actions, deposit approvals. Replays return the original
   result; nothing duplicates.
4. **Concurrency.** Wallet rows are locked with `select_for_update()`
   inside atomic blocks; duplicate/concurrent submissions are covered by
   per-app concurrency tests plus the Section 14 suite.
5. **Reconciliation.** `python manage.py reconcile_wallets [--user X]
   [--strict]` compares every wallet against its ledger and *reports*
   drift (detect/report/audit — never silently rewrites balances).
6. **Decimal everywhere.** Monetary values are `DecimalField`s end to end;
   no `float` money math exists in app code.
7. **No fabricated blockchain data.** A withdrawal completion either records
   a real on-chain transaction hash (hex-validated at the service layer) or
   none at all; the platform never invents hashes or confirmations. Deposit
   crediting likewise occurs only after admin review — or, once a chain
   provider is configured and `CHAIN_VERIFICATION_ENABLED=True`, after
   independent on-chain verification.

## Authorization model

| Surface | Anonymous | User | Admin (staff) |
| --- | --- | --- | --- |
| Auth (`/api/auth/*`) | register/login/refresh | ✓ | ✓ |
| Wallet/transactions | ✗ 401 | own rows only | via admin ledger API |
| Deposits | ✗ 401 | own deposits; submit only | approve/reject (Section 6/12 APIs) |
| Withdrawals | ✗ 401 | own; submit (throttled) | state machine via admin APIs |
| VIP / rewards | ✗ 401 | own plans/purchases/rewards | plan CRUD, retries |
| Referrals | ✗ 401 | own team/commissions | read-only lists |
| Support | ✗ 401 | own conversations | staff reply/status (GroupPermission) |
| Notifications | ✗ 401 | own only (IDOR 404s) | broadcast (GroupPermission) |
| Admin (`/api/admin/*`) | ✗ 401 | ✗ 403 | `IsAdminUser` + group checks |

Every admin endpoint re-checks permissions server-side (`IsAdminUser`
plus `GroupPermission` for dangerous actions); the frontend `RequireAdmin`
route guard is convenience only. There is **no wallet-balance editing**
anywhere; adjustments exist only as audited service-level `admin_adjust`
operations with ledger entries.

## Secret management

- All secrets come from environment variables (`backend/.env`, git-ignored;
  `backend/.env.example` holds placeholders only).
- `config/settings/prod.py` **refuses to boot** with the development
  fallback `SECRET_KEY`, empty `ALLOWED_HOSTS`, or empty
  `CORS_ALLOWED_ORIGINS`.
- No credentials in the repo, README, or frontend bundle; `dump.rdb` and
  `*.rdb` are git-ignored.

## Production settings (`config.settings.prod`)

Enabled when `DJANGO_SETTINGS_MODULE=config.settings.prod`:
`DEBUG=False`, `SECURE_SSL_REDIRECT`, HSTS (1y, include-subdomains,
preload), secure session/CSRF cookies, `X_FRAME_OPTIONS=DENY`,
`SECURE_CONTENT_TYPE_NOSNIFF`, `strict-origin-when-cross-origin` referrer
policy, production throttle rates, and safe error pages (no tracebacks).

CORS is an explicit allow-list (no `CORS_ALLOW_ALL_ORIGINS`); CSRF trusted
origins are explicit; do not enable SSL/HSTS flags until HTTPS is actually
terminated for the deployment.

## Input/output security

- DRF serializers declare explicit fields; sensitive model fields
  (`is_staff`, `is_superuser`, `account_status`, balances, approval state)
  are read-only or absent. Mass-assignment escalation is covered by tests.
- All list endpoints paginate; filters are validated against choice sets;
  search uses parameterized ORM lookups only (no raw SQL anywhere in app
  code).
- User text is rendered as plain text (React escaping); support messages
  are length-limited, scheme-filtered, and rate-limited; notification
  content is plain text with no HTML pathway.
- Errors return the standard `{success, message, errors}` envelope; stack
  traces never reach clients (`DEBUG=False` + custom exception handler).

## Rate limiting

- Login: `10/min` scope + per-identifier/IP counters with lockout.
- Password reset: `5/min`.
- Financial writes (deposit submit, withdrawal create, VIP purchase):
  `fin_write` = `30/min` shared scope (returns HTTP 429).
- Support messaging: per-user fixed-window counters in the service layer.
- Global anon `100/min` (dev) / `60/min` (prod), user `1000/min`.

## Testing

```bash
cd backend
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test apps.core.tests_security --noinput   # Section 14 suite
python manage.py test                                      # full suite
cd ../frontend && npm run build                            # tsc + vite build
npm audit --omit=dev                                       # 0 known vulnerabilities
```

The Section 14 suite (`apps/core/tests_security.py`, 30 tests) covers:
account-status enforcement, the cross-app IDOR matrix, admin
authorization for every admin surface, privilege-escalation/mass-assignment
probes, financial-write throttles (429), reconciliation-based accounting
invariants, drift detection, withdrawal lifecycle invariants, duplicate-
purchase idempotency, the no-fabricated-hash rule, and a static guard
against direct wallet mutations.

`pip-audit` is not installed in this environment; run it in CI
(`pip install pip-audit && pip-audit -r backend/requirements.txt`) rather
than assuming the backend dependency tree is clean.

## Reporting vulnerabilities

There is no bug-bounty program or published security contact yet. Do not
enable real-funds flows before the integration gates, compliance review, and
infrastructure items below are complete.

## Real-funds activation gates (current limitations)

Balances change only through audited ledger events, but **real-world financial
integrations are disabled by default** and must each be satisfied before
activation:

- `CHAIN_VERIFICATION_ENABLED` — off; no chain-access provider is configured.
- `PAYOUTS_ENABLED` — off; no custody/payout provider is configured.
- `REWARD_PAYOUTS_ENABLED` — off; the reward scheme awaits legal review.
- `KYC_REQUIRED_FOR_WITHDRAWALS` — off; no identity-verification provider is
  configured, and `kyc_status=APPROVED` can only ever be set by such a
  provider event.
- No FIU-IND (or equivalent) registration, no legal/compliance sign-off, no
  penetration test, and no tested backup/restore drill exist yet.

## Production checklist

Only tick an item after verifying it in the target environment.

- [ ] `DEBUG=False` (prod settings enforce)
- [ ] Strong per-environment `SECRET_KEY` (prod settings refuse fallback)
- [ ] `ALLOWED_HOSTS` set to real domains
- [ ] CORS restricted to the real frontend origin
- [ ] CSRF trusted origins configured
- [ ] HTTPS terminated; `SECURE_SSL_REDIRECT`/HSTS enabled
- [ ] Secure cookies active (prod settings enforce under HTTPS)
- [ ] Database credentials secured (env vars, network-restricted Postgres)
- [ ] Redis bound to loopback/private network, auth enabled if exposed
- [ ] All environment variables configured from `.env.example`
- [ ] `makemigrations --check` clean; migrations applied
- [ ] Full backend test suite green
- [ ] Frontend build green
- [ ] Dependency audit reviewed (`npm audit`, `pip-audit` in CI)
- [ ] Backups configured and restore-tested (documented below)
- [ ] Logging reviewed — no secrets/tokens in log output
- [ ] Admin group permissions reviewed (`bootstrap_admin_groups`)
- [ ] Rate limits reviewed for expected traffic
- [ ] Error pages configured (DEBUG=False, safe envelope)
- [ ] Real-funds activation gates (above) reviewed and deliberately enabled
- [ ] Honest, supportable financial claims verified (no fabricated activity)

### Backup readiness (documentation, not yet configured)

No backups are currently operational — document before any real deployment:

- **PostgreSQL**: nightly `pg_dump -Fc` to off-host storage; retain ≥ 7
  daily + 4 weekly; restore drill = `pg_restore` into a scratch database
  and run `reconcile_wallets` against it.
- **Environment separation**: dev/staging/prod databases and Redis are
  separate; never point dev tooling at production data.
- **Redis**: cache/throttle/broker data only — loss is acceptable; do not
  treat it as durable.
