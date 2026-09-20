# Deployment Guide

Deployment preparation for the **NexusUSDT platform**. This document describes
the expected production topology and every configuration surface; it
deliberately contains **no real credentials or domains** — replace
placeholders (`app.example.com`, `api.example.com`) with the values chosen by
the project owner.

> Reminder: real-funds flows (chain verification, automated payouts, reward
> automation, KYC) ship disabled and must not be enabled without independent
> legal, compliance, and security review — see `docs/SECURITY.md` for the
> activation gates.

---

## 1. Prerequisites

- Linux server(s) or PaaS instances
- Python 3.11, Node.js 20+, PostgreSQL 16, Redis 7+
- A reverse proxy with TLS termination (nginx, Caddy, or the PaaS equivalent)
- Process manager (systemd, or containers) for API + Celery processes

## 2. Environment configuration

Copy `backend/.env.example` → `backend/.env` and fill in **real** values.
Every secret comes from the environment — never commit `.env`.

| Variable | Production expectation |
| --- | --- |
| `DJANGO_SETTINGS_MODULE` | `config.settings.prod` |
| `DEBUG` | `False` |
| `SECRET_KEY` | 50+ random chars, unique per environment (prod **refuses** dev fallbacks) |
| `ALLOWED_HOSTS` | `api.example.com` |
| `DATABASE_URL` | `postgresql://user:pass@db-host:5432/dbname` |
| `REDIS_URL` | `redis://:password@redis-host:6379/0` |
| `CORS_ALLOWED_ORIGINS` | `https://app.example.com` (exact origin list) |
| `CSRF_TRUSTED_ORIGINS` | `https://app.example.com` |
| `PUBLIC_APP_URL` | `https://app.example.com` (referral links) |
| `MAX_UPLOAD_BYTES` | optional; default 5242880 (5 MB) image cap |
| `CHAIN_VERIFICATION_ENABLED` | keep `False` until a real chain provider is wired in |
| `PAYOUTS_ENABLED` | keep `False` until a real payout provider is wired in |
| `SECURE_SSL_REDIRECT` | `True` once HTTPS is live |

Frontend build-time variables (`frontend/.env.production`, public only):

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | `https://api.example.com/api` (empty = same-origin `/api`) |

Never place secrets in `VITE_*` variables — they ship to every browser.

## 3. Database (PostgreSQL)

```bash
createdb -h db-host -U app_user usdt_prod
cd backend
python manage.py migrate --noinput          # apply schema
python manage.py bootstrap_deposit_networks # create Network rows (NO addresses)
python manage.py bootstrap_admin_groups     # admin permission groups
python manage.py seed_platform_settings     # editable settings rows (defaults)
python manage.py createsuperuser            # first admin account
```

### Post-migrate: configure deposit networks (operator, REQUIRED)

`bootstrap_deposit_networks` creates the six USDT network rows (BSC, TRX,
ETH, POL, SOL, TON) with **empty configuration** — it never invents deposit
addresses. Before users can deposit on a network, the operator must set,
per network, via the admin panel (`/admin` → Networks / Deposit addresses):

1. **Deposit address** — your real receiving address for that network
   (POST `/api/admin-panel/deposit-addresses/` with `{network, address}`).
2. **Contract address** (optional display) — e.g. the USDT contract on that
   chain.
3. **Per-network minimum deposit / minimum withdrawal / withdrawal fee** —
   optional; leave empty to inherit the global `deposit.min_amount` and
   `withdrawal.*` settings.
4. **Warning / instructions** — user-facing copy shown on the deposit and
   withdrawal pages (a strong default warning renders when empty).
5. **Enabled** — activate the network only after its address is configured.

Uploaded files (deposit screenshots, withdrawal QR images) are stored under
`MEDIA_ROOT` in **private media** and served only through authenticated
staff/owner views — never expose `media/` on a public static path.

Notes:

- `seed_demo_data` (configuration reference rows) is for **development** and
  is blocked in production; create the real `Network`, `DepositAddress`, and
  `VIPPlan` rows through the admin panel instead. Never copy development
  financial activity into a production database.
- Connection settings: `CONN_MAX_AGE=60` is already configured; put pgbouncer
  in front if the deployment needs heavy pooling.

### Backups (documented in SECURITY.md; not yet automated)

- Nightly: `pg_dump -Fc usdt_prod > backups/usdt_prod_$(date +%F).dump`
- Retention: ≥ 7 daily + 4 weekly, off-host storage
- **Restore drill** (a backup counts as usable only after this passes):
  `pg_restore` into a scratch database, point a staging `DATABASE_URL` at it,
  run `python manage.py migrate --check` and `reconcile_wallets --strict`.
- Rollback of a bad migration: restore the pre-migration dump; Django has no
  safe automatic downgrade path.

## 4. Redis + Celery

Architecture:

```
Frontend ──▶ Django API ──▶ PostgreSQL
                 │
                 ▼
               Redis ◀── Celery Worker   (retries, async jobs)
                 ▲
           Celery Beat ── daily VIP reward cycle (00:15)
```

- Redis binds to loopback/private network only; set a password in production
  (`REDIS_URL=redis://:password@host:6379/0`).
- **Exactly one Beat instance** may run fleet-wide — two would double-fire
  schedules (the reward engine is idempotent, but don't rely on it).
- systemd units (or container equivalents):

```ini
# celery-worker.service
ExecStart=/opt/venv/bin/celery -A config worker -l info --concurrency=2
# celery-beat.service (single instance only)
ExecStart=/opt/venv/bin/celery -A config beat -l info --schedule /var/run/celery/beat-schedule
```

## 5. Backend deployment

```bash
git pull
python -m venv /opt/venv && /opt/venv/bin/pip install -r backend/requirements.txt
python manage.py check --deploy      # Django's own production audit
python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
systemctl restart gunicorn celery-worker celery-beat
```

Serve with gunicorn behind the TLS-terminating proxy:

```bash
gunicorn config.wsgi:application --workers 4 --bind 127.0.0.1:8000
```

## 6. Frontend deployment

```bash
cd frontend
npm ci
npm run build          # outputs dist/ (includes the SPA _redirects file)
```

Deploy `dist/` to the static host/CDN. SPA rewrites: route all paths to
`/index.html` (404s are handled client-side). Set
`VITE_API_BASE_URL=https://api.example.com/api` at build time when the API
lives on a separate domain.

### Netlify (recommended path for this repo)

The SPA rewrite already ships as `frontend/public/_redirects` and lands in
`dist/` on build, so deep links like `/admin` resolve correctly.

1. Push the repository to GitHub/GitLab.
2. In Netlify: **Add new site → Import an existing project**, pick the repo.
3. Build settings:
   - Base directory: `frontend`
   - Build command: `npm run build`
   - Publish directory: `frontend/dist`
4. Environment variables (Site configuration → Environment variables):
   - `VITE_API_BASE_URL=https://api.example.com/api` (your real API origin;
     leave unset only if you also proxy `/api` via a Netlify redirect —
     see the note below).
5. Deploy. Netlify serves the build over HTTPS with a `*.netlify.app`
   domain; attach a custom domain under **Domain management** when ready.

Optional same-origin API (avoids all CORS/cookie complexity): add a
redirect in `frontend/public/_redirects` proxying to the backend host —

```text
/api/*   https://api.example.com/api/:splat   200
```

…and then leave `VITE_API_BASE_URL` unset so the client calls `/api` on its
own origin. (Netlify proxying requires a paid plan for high volume; the
split-domain setup below is the free-tier default.)

What the BACKEND needs when the frontend is on `*.netlify.app` (split
domains) — set these on the Django host:

- `CORS_ALLOWED_ORIGINS=https://<site>.netlify.app` (exact origin)
- `CSRF_TRUSTED_ORIGINS=https://<site>.netlify.app`
- `REFRESH_COOKIE_SAMESITE=None` (required when the API domain is not
  subdomain-related to the frontend domain; HTTPS is mandatory, which
  Netlify provides)
- The refresh cookie is already `HttpOnly`, `Secure` outside `DEBUG`, and
  scoped to `/api/auth/`.

## 7. Domain, HTTPS, cookies

```
https://app.example.com   → static frontend (CDN)
https://api.example.com   → gunicorn (Django API)
```

- Terminate TLS at the proxy; `config.settings.prod` then enables
  HSTS (1 year, preload), `SECURE_SSL_REDIRECT`, and secure session/CSRF
  cookies automatically.
- CORS/CSRF allow-lists must list the exact frontend origin (scheme +
  host + port).
- Cookies: `SameSite=Lax` by default (`REFRESH_COOKIE_SAMESITE=None` when
  frontend and API sit on unrelated domains); refresh token cookie is
  `HttpOnly` + `Secure` outside development; CSRF cookie stays readable by
  JS for the double-submit header.

## 8. Health checks

- `GET /api/health/` → `{"status": "ok"}` — dependency-free liveness probe.
  Wire the load balancer / uptime monitor to it.
- Do **not** expose DB/Redis diagnostics publicly; the endpoint intentionally
  reports nothing else.

## 9. Logging & monitoring (recommended, not yet wired)

Current state: structured console logging (`config.settings.prod` LOGGING),
Django security loggers, and an application `AuditLog` trail (admin-visible).
Not yet configured — integrate before launch:

- Error tracking (e.g. Sentry SDK) for exceptions and Celery failures
- Uptime monitoring on `/api/health/`
- Log shipping to a retained sink; never log tokens, passwords, or keys

## 10. Post-deployment smoke test

Run through these in order (read-only checks first):

1. `GET https://api.example.com/api/health/` → ok
2. Signup → login → dashboard loads with wallet summary
3. Deposit: network selector shows configured networks with per-network
   minimums; address + server-rendered QR match; submit → PENDING
4. Duplicate transaction hash (same or different user) is rejected
5. Admin: deposit appears with screenshot (if uploaded) and
   "Manual verification" label → approve → ledger row + wallet credit
   exactly once → second approve is a no-op
6. Admin: reject → reason stored + user notified; the hash may be reused
   after rejection
7. VIP purchase from withdrawable balance → snapshot correct
8. Reward cycle (or `process_vip_rewards` manually) → one credit per cycle
9. Withdrawal: submit → funds LOCKED immediately (withdrawable ↓, locked ↑);
   insufficient balance rejected atomically; invalid network/address format
   rejected server-side
10. Admin withdrawal queue: approve → "Payment pending" state visible →
    processing → complete with the REAL payout transaction hash (never
    invented; an empty hash is allowed only when settlement is internal) →
    status COMPLETED, locked balance finalized exactly once
11. Admin rejects a withdrawal → reserved balance released, reason stored,
    user notified
12. Referral commission fires on the referrer's side once, not twice
13. Support reply → user notification arrives
14. Notifications: unread count, mark-read, mark-all
15. Transaction history filters/search paginate correctly
16. `/admin/*` rejects non-staff users (401/403)

Destructive/security tests belong in **staging**, never against production
data.

## 11. Pre-deployment checklist

- [ ] All environment variables set from `.env.example` with real values
- [ ] Production database created; migrations applied
- [ ] Redis reachable with password; **single** Celery Beat instance
- [ ] Celery worker running
- [ ] `DEBUG=False` (prod settings enforce)
- [ ] CORS/CSRF restricted to the real origin
- [ ] HTTPS live; HSTS/secure cookies active
- [ ] Domain + `VITE_API_BASE_URL` configured
- [ ] Secrets stored in a secret manager; `.env` not in git
- [ ] Backups scheduled **and restore drill passed**
- [ ] Monitoring/error tracking wired to `/api/health/` + exceptions
- [ ] `python manage.py check --deploy` clean
- [ ] Full backend test suite green; frontend build green
- [ ] No fabricated financial activity or claims; empty states remain empty

## 12. Rollback

1. Frontend: redeploy the previous `dist/` artifact (immutable builds).
2. Backend: redeploy the previous release tag; migrations are append-only —
   if a migration must be reverted, restore the pre-deploy database dump
   (see restore drill above).
3. Redis: cache/throttle/broker data is disposable; flush if corrupted.

## 13. Post-deployment security re-check

Repeat in staging: IDOR probes, privilege-escalation probes, throttle 429s,
withdrawal state-machine rejections, reconciliation (`--strict`), dependency
audit (`npm audit`, `pip-audit`). Production gets only the read-only smoke
tests above.
