# Architecture Notes (Section 1)

This document captures the structural decisions made in Section 1 so later
sections can extend the system without reworking the foundation.

## High-level shape

```text
┌─────────────────┐        /api/* (JSON)        ┌──────────────────┐
│  React SPA      │ ───────────────────────────▶│  Django + DRF    │
│  (Vite build)   │ ◀───────────────────────────│  apps/*          │
└────────┬────────┘                             └────────┬─────────┘
         │                                               │
         │  Axios (services/)                            │  ORM
         ▼                                               ▼
   Vite dev proxy                                  PostgreSQL 16
   → http://127.0.0.1:8000
                                                         ▲
   Celery workers ──▶ Redis (broker + results) ──────────┘
```

## Backend

- **`config/settings/` package** — `base.py` holds shared configuration;
  `dev.py` (default) relaxes errors for development. Environment-specific
  settings are selected via `DJANGO_SETTINGS_MODULE`.
- **`apps/` package** — every domain app uses the `apps.` label
  (`apps.accounts`, `apps.wallet`, …) to keep the import namespace flat and
  predictable.
- **`apps.core`** — cross-cutting concerns only: `/api/health/` and shared
  Celery tasks. Domain logic must not live here.
- **API prefix** — all endpoints mount under `/api/` via
  `apps.core.urls` → later apps include their own `urls.py` there.
- **Celery** — the app is instantiated in `config/celery.py`, imported from
  `config/__init__.py`, and configured from Django settings with the
  `CELERY_` namespace. Tasks autodiscover from each app's `tasks.py`.
- **Throttling** — DRF anon/user rate limits are on by default; tighten
  per-endpoint as sensitive endpoints land.

## Frontend

- **Path alias** — `@/` maps to `src/` (tsconfig + Vite).
- **Routing** — a single data router in `src/routes/index.tsx`
  (`createBrowserRouter`). Public routes use `PublicLayout`; authenticated
  routes use `DashboardLayout` with a mobile bottom nav. `/admin/*` mounts a
  separate lazy route tree (`src/routes/adminRoutes.tsx`) behind a staff gate
  and its own `AdminLayout` (Section 12).
- **Code splitting** — every page is a lazy route; the landing page loads
  eagerly for fast first paint.
- **API layer** — `src/services/api.ts` is the only module allowed to touch
  Axios. Errors are normalized to `ApiError { status, message, detail }` so
  UI code never parses Axios errors.
- **Design system** — `src/components/` holds the primitives (Button, Card,
  Input, Badge, Modal, Alert, EmptyState, ErrorState, Spinner,
  PageContainer). Tokens (brand/accent/surface palettes, shadows, motion)
  live in `tailwind.config.js`.

## Module docs

- `WALLET.md` — wallet/ledger system (Section 5)
- `WITHDRAWALS.md` — withdrawal system (Section 10)
- `ACCOUNT_SUPPORT.md` — account & support (Section 11)
- `ADMIN_PANEL.md` — admin panel (Section 12)
- `NOTIFICATIONS_TRANSACTIONS.md` — notifications & transaction history (Section 13)
- `SECURITY.md` — security architecture, rules & production checklist (Section 14)

## Development services

`docker-compose.yml` runs PostgreSQL 16 + Redis 7 with healthchecks and
named volumes. On hosts without Docker, both services can run natively —
the connection settings come from `backend/.env` either way.

## Rules carried into later sections

1. Financial mutations: explicit `transaction.atomic()` blocks.
2. Money movements: idempotency keys + audit trail rows.
3. No client-side balances — the API is the single source of truth.
4. Deposit addresses are generated per-request at runtime, never hard-coded.
