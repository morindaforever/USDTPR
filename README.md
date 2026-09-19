# NexusUSDT — USDT Platform

A production-quality, mobile-first web platform for USDT deposits, VIP tiers,
and referral rewards. Built section by section — **all 15 sections are
complete**: foundation, database, auth, dashboard, wallet ledger, deposits,
VIP system, reward engine, referrals, withdrawals, account & support, admin
panel, notifications & transaction history, security hardening, and UI
polish/deployment prep.

> **Status note.** This codebase implements real accounting (wallet ledger,
> idempotency, audit trail) but external financial integrations are disabled
> by design until real providers are configured: no chain verification, no
> automated payouts, no reward automation, and no KYC provider are active
> (see `docs/SECURITY.md` and the integration gates in `backend/.env.example`).
> Nothing here is financial advice, a promise of returns, or an offer of
> services. Cryptocurrency involves risk.

---

## Tech stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, Vite 5, TypeScript 5, Tailwind CSS 3, React Router 7, Axios, Lucide icons |
| Backend | Python 3.11, Django 4.2, Django REST Framework 3.15 |
| Database | PostgreSQL 16 |
| Background jobs | Redis 7/8 + Celery 5 |
| Services (optional) | Docker Compose (PostgreSQL + Redis) |

---

## Project structure

```text
project-root/
├── frontend/                 # React SPA (Vite + TypeScript + Tailwind)
│   ├── public/
│   ├── src/
│   │   ├── components/       # Design system (Button, Card, Input, Modal, …)
│   │   ├── layouts/          # DashboardLayout, PublicLayout, Header, BottomNavigation
│   │   ├── pages/            # Route pages (public, auth, dashboard)
│   │   ├── routes/           # Central route table
│   │   ├── services/         # API modules (api.ts + feature services)
│   │   ├── hooks/            # Shared React hooks
│   │   ├── utils/            # Formatting / classname helpers
│   │   ├── types/            # Shared TypeScript interfaces
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
│
├── backend/                  # Django project
│   ├── config/               # Project settings (base/dev), URLs, Celery app
│   ├── apps/                 # Domain apps (models arrive in later sections)
│   │   ├── core/             # /api/health/, shared tasks  ← has code now
│   │   ├── accounts/
│   │   ├── wallet/
│   │   ├── deposits/
│   │   ├── withdrawals/
│   │   ├── vip/
│   │   ├── referrals/
│   │   ├── support/
│   │   ├── notifications/
│   │   └── adminpanel/
│   ├── manage.py
│   ├── requirements.txt
│   └── .env.example
│
├── docs/                     # Architecture & runbooks
├── docker-compose.yml        # PostgreSQL + Redis for local dev
├── .env.example              # Compose service credentials
└── .gitignore
```

---

## Prerequisites

- **Node.js 18+** and npm
- **Python 3.11+**
- **PostgreSQL 14+** (local install, or via `docker-compose.yml`)
- **Redis 6+** (local install, or via `docker-compose.yml`)

Optionally, start just the services with Docker and run the apps natively:

```bash
docker compose up -d
```

---

## 1. Environment variables

Backend — copy and edit (defaults work for local development):

```bash
cd backend
cp .env.example .env
```

Frontend — only needed if you don't use the Vite proxy:

```bash
cd frontend
cp .env.example .env.local   # set VITE_API_BASE_URL if needed
```

Never commit real `.env` files — they are git-ignored.

---

## 2. Backend setup

macOS / Linux:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Windows:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The API is now at `http://127.0.0.1:8000`, and the health check at
`http://127.0.0.1:8000/api/health/` should return `{"status": "ok"}`.

### PostgreSQL setup

```sql
CREATE DATABASE usdt_platform;
CREATE USER usdt_platform WITH PASSWORD 'usdt_platform';
GRANT ALL PRIVILEGES ON DATABASE usdt_platform TO usdt_platform;
```

Adjust `DATABASE_URL` in `backend/.env` if your credentials differ. With the
bundled Docker Compose, the defaults already match.

### Redis setup

Nothing to configure beyond a running instance — `REDIS_URL` in
`backend/.env` points to `redis://localhost:6379/0` by default.

---

## 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/api/*` to Django, so
no CORS setup is needed in development.

---

## 4. Celery setup

In a second terminal (with the venv active):

```bash
cd backend
celery -A config worker -l info
```

Windows users should add `--pool=solo`:

```bash
celery -A config worker -l info --pool=solo
```

Run the smoke task from a Django shell to verify the full broker round-trip:

```bash
python manage.py shell
>>> from apps.core.tasks import test_celery_task
>>> result = test_celery_task.delay()
>>> result.get(timeout=30)
{'success': True, 'message': 'Celery is working!', ...}
```

---

## 5. Running tests

Backend (full suite):

```bash
cd backend
python manage.py test
```

Or per app, e.g. `python manage.py test apps.vip`, `apps.wallet`,
`apps.deposits`, `apps.core`, `apps.accounts`.

Seed the configuration reference rows (networks, the 8 VIP plans, withdrawal
rules — configuration only, no financial activity; dev/test environments only):

```bash
python manage.py seed_demo_data
```

Frontend (typecheck + production build):

```bash
cd frontend
npm run typecheck
npm run build
```

---

## 5b. Security & financial integrity

See [`docs/SECURITY.md`](docs/SECURITY.md) for the full picture. Highlights:

- All balance changes flow through one wallet service; the
  `WalletTransaction` ledger is the source of truth and is reconcilable via
  `python manage.py reconcile_wallets [--strict]`.
- Idempotency keys on every retry-sensitive financial operation;
  `select_for_update()` for concurrent money movement.
- Account status (ACTIVE/SUSPENDED/BANNED) enforced server-side; IDOR,
  privilege-escalation, throttle, and reconciliation tests live in
  `backend/apps/core/tests_security.py`.
- Hardened production settings: `DJANGO_SETTINGS_MODULE=config.settings.prod`
  (refuses weak `SECRET_KEY`, enables HSTS/secure cookies/HTTPS redirect).

---

## 6. API overview

| Endpoint | Method | Description |
| --- | --- | --- |
| `/api/health/` | GET | Liveness probe — `{"status": "ok"}` |
| `/api/auth/register/` · `login/` · `logout/` · `refresh/` · `me/` | POST/GET | Authentication (Section 3) |
| `/api/auth/forgot-password/` · `reset-password/` · `change-password/` | POST | Password flows (Section 3) |
| `/api/wallet/summary/` | GET | Authenticated user's wallet buckets (Section 5) |
| `/api/wallet/transactions/` | GET | Own ledger, paginated + filterable (Section 5) |
| `/api/wallet/transactions/<transaction_id>/` | GET | Own transaction detail (Section 5) |
| `/api/deposits/networks/` | GET | Active deposit networks (Section 6) |
| `/api/deposits/address/` | GET | Active deposit address for a network (Section 6) |
| `/api/deposits/` | POST/GET | Submit deposit; own deposit history (Section 6) |
| `/api/deposits/<deposit_id>/` | GET | Own deposit detail (Section 6) |
| `/api/admin/deposits/` · `<id>/` | GET | Admin deposit list/detail (Section 6, staff only) |
| `/api/admin/deposits/<id>/approve/` · `reject/` | POST | Manual deposit review (Section 6, staff only) |
| `/api/admin/deposit-addresses/` | GET/POST/PATCH | Address manager; deactivate→re-add to rotate (Section 6, staff only) |
| `/api/vip/plans/` · `plans/<id>/` | GET | Active VIP plans; detail (Section 7) |
| `/api/vip/plans/<id>/summary/` | GET | Purchase confirmation data, server-computed (Section 7) |
| `/api/vip/purchase/` | POST | Buy a plan (idempotency key required) (Section 7) |
| `/api/vip/active/` · `purchases/` | GET | Own active plans (with reward progress); full history (Section 7) |
| `/api/vip/rewards/` · `rewards/<reward_id>/` | GET | Own reward history; owner-only detail (Section 8) |
| `/api/vip/current/` | GET | Active plan snapshot + reward progress (Section 4/8) |
| `/api/referrals/summary/` | GET | Referral code/link, team counts, commission totals (Section 9) |
| `/api/referrals/direct/` · `team/` | GET | Level-1 referrals; paginated team with level/status/search filters (Section 9) |
| `/api/referrals/commissions/` · `<id>/` | GET | Own commission history (filters + pagination); owner-only detail (Section 9) |
| `/api/site/valuation/` | GET | Legacy valuation series (excludes seed-flagged rows; not rendered in the UI) |

Balance mutations are internal services only — see `docs/WALLET.md` for the
wallet/ledger architecture, accounting rules, and reconciliation tooling.

---

## 7. Deposit system (Section 6)

Deposits are **manually reviewed by an admin** — there is no blockchain
verification and no automatic crediting. Flow: user picks a network → gets
the active address → sends USDT on that exact network → submits the amount
and TX hash → deposit is `PENDING` → admin approves or rejects in the admin
API. Approval is the only path to a wallet credit, and it goes through the
Section 5 wallet service (ledger row + notification + audit log, all in one
transaction). Repeat approvals/rejections are rejected server-side; amounts
are exact `Decimal(24, 8)` values end to end.

Admin address rotation is append-only: deactivate the old address and add a
new one — historical deposits keep referencing the address they were made
to. Dev/test environments can use clearly-marked test networks/addresses;
never mix them with production addresses.

---

## 8. VIP system (Section 7)

`/vip` lists the configured plans (Welcome + VIP 1–7, 25% daily rate from
configuration). Purchasing runs through the wallet service inside one atomic
transaction: lock wallet → validate plan/balance → debit → create the
`VIPPurchase` **with the plan terms snapshotted** (later plan edits never
rewrite history) → ledger `VIP_PURCHASE` row → audit log → notification.

Purchases are idempotent: the client sends an `idempotency_key`; replays
return the original purchase without a second debit. The Welcome plan
is free and can be claimed once per user (partial-unique constraint guards
concurrent claims). The confirmation modal's balance figures come from
`GET /api/vip/plans/<id>/summary/`, never from the browser. Reward/mining
progress is intentionally **not** implemented — active plans show
"Reward tracking starts in the next system cycle" until that section lands.

> Plan numbers are configuration values, not offers. Nothing on the platform
> is a promise of, or a guarantee of, investment returns.

---

## 9. Reward engine (Section 8)

The daily reward run is the **only** way VIP rewards are credited, and
it never touches wallet columns directly — it calls the Section 5 wallet
service, which writes the ledger row and balance atomically:

```text
Celery beat (00:15 project time) → vip.process_daily_vip_rewards
    → reward_service.process_daily_rewards(cycle)
        → process_reward(purchase, cycle)   [atomic: lock purchase row]
            → wallet service credit()        (Section 5)
```

Rules encoded in `apps/vip/reward_service.py`:

- **Cycle** — one calendar day in the project timezone (`timezone.localdate`,
  never `datetime.now()`).
- **Formula** — `daily = investment × daily_rate`, Decimal only, quantized to
  the wallet's 8-dp precision, computed from the **purchase's snapshotted
  terms** (later `VIPPlan` edits never change history).
- **Target cap** — `actual = min(daily, target − rewarded)`; at the cap the
  purchase flips to `COMPLETED` atomically and stops accruing.
- **Idempotency** — deterministic wallet key `VIP_REWARD_<purchase>_<cycle>`
  plus a DB unique constraint on `(vip_purchase, reward_date)`. Beat double
  ticks, Celery retries, and manual re-runs can never credit a cycle twice.
- **Concurrency** — `select_for_update` on the purchase row; racing workers
  serialize, losers observe the committed reward and skip.
- **Failure safety** — a wallet error commits the reward as `FAILED` (no
  money moved) and re-raises; a later retry reclaims and reprocesses it.

Manual run for development/testing (same service as Celery — no duplicate
logic):

```bash
python manage.py process_vip_rewards                      # current cycle
python manage.py process_vip_rewards --cycle-date 2026-09-16
```

User-facing surfaces: `/vip` shows per-plan progress (rewarded / target /
percent from `GET /api/vip/active/`), a reward history section
(`GET /api/vip/rewards/`), and the dashboard's Current Plan card exposes the
same backend-computed progress plus the next scheduled run time. Rewards
appear in the normal wallet transaction history as `VIP_REWARD` credits.

> Reward credits reflect the configured scheme only. They are not
> investment returns and carry no guarantees. Scheduled automation stays
> disabled (`REWARD_PAYOUTS_ENABLED=False`) until the scheme is legally
> reviewed and authorized.

---

## 10. Referral / team system (Section 9)

Every user gets a unique code at signup; the shareable link is built from
the `PUBLIC_APP_URL` environment setting (never a hard-coded domain):
`{PUBLIC_APP_URL}/signup?ref=<CODE>`. Opening it prefills the signup form;
the backend re-validates everything (code exists, referrer account ACTIVE,
no self-referral, no duplicate referrer, no cycles) and creates the
`Referral` relationship — never a commission.

**Commission source:** eligible **VIP rewards only** (§12). When the
Section 8 engine credits a reward, it hands the reward to the referral
engine post-commit:

```text
reward credited → walk referred_by upward (bounded by referral.max_level, default 3)
    → per ACTIVE ancestor, one atomic block:
        ReferralCommission (rate/level/amount SNAPSHOTTED)
        → wallet service credit()  (Section 5)  → REFERRAL_COMMISSION ledger row
        → audit log + notification
```

Guarantees:

- **Idempotency** — deterministic key `REF_COMM_<reward>_<user>_<level>`
  with a UNIQUE column; Celery retries, reward re-runs, and racing workers
  can never pay a commission twice.
- **Isolation** — one ancestor failing (wallet error) records a FAILED row
  and never corrupts the reward or other levels; retries repay FAILED rows.
- **Snapshots** — historical commissions keep their original rate/amount
  even after `referral.level_N_rate_percent` SiteSettings change.
- **No commissions from** registrations, deposits, withdrawals, or other
  commissions (§36–38, §77).

Commission rates (SiteSetting-editable, defaults): Level 1 = 10%, Level 2 = 5%,
Level 3 = 2%, `referral.max_level` = 3 (hard bound 5). Rates are stored as
fractions on commissions (0.10) and shown as percentages in the UI.

Team data (`/team` page + `/api/referrals/*`) is derived from persisted
rows only, with user-ID/name projections — no emails or wallet data.

> Commission figures come from the reward engine's configuration —
> not real or guaranteed income.

---

## Development conventions

1. No business logic in React components — it lives in services/hooks.
2. All API communication goes through `frontend/src/services/`.
3. Django business logic lives in its app's `services/`/`tasks.py` modules.
4. Secrets and connection details come from environment variables only.
5. Passwords are never stored in plaintext; wallet addresses and balances
   are never hard-coded.
6. Financial operations (deposits, VIP purchases, and later modules) use DB
   transactions, idempotency keys, and full auditability.
