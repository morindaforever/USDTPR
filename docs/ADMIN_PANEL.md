# Admin Panel (Section 12)

Centralized staff console at `/admin` for every system built in Sections 1–11.
Completely separated from user functionality: dedicated layout, dedicated API
surface (`/api/admin/*`), and per-action permission groups.

## Access

- Route: `/admin` (all sub-pages require authentication).
- Unauthenticated → redirected to `/login`. Non-staff → redirected to `/home`
  (presentation only — the backend independently returns 403).
- Create an admin:

```bash
python manage.py createsuperuser        # sets is_staff/is_superuser
python manage.py bootstrap_admin_groups # creates permission groups (idempotent)
python manage.py seed_platform_settings # seeds editable settings rows (idempotent)
```

## Backend architecture (`backend/apps/adminpanel/`)

| Module | Contents |
| --- | --- |
| `permissions.py` | `IsAdminUser` gate + `GroupPermission` (least-privilege groups). |
| `permissions_config.py` | Action → required-group map used by bootstrap. |
| `dashboard_views.py` | Aggregated stats with server-side date ranges (today/7d/30d/all/custom). |
| `user_views.py` | User list (search/filter/paginate), detail, `status` actions, per-user history. |
| `finance_views.py` | Deposits (reuses Section 6 approval), withdrawals (reuses Section 10 state machine), VIP plans CRUD, purchases, rewards (process/retry), transactions. |
| `ops_views.py` | Referrals, commissions, support management, notifications + broadcast, audit logs, settings. |
| `serializers.py` | Explicit whitelisted fields — mass assignment impossible. |
| `urls.py` | All routes under `/api/admin/`. |

### Permission groups (§65–66)

`bootstrap_admin_groups` creates: **User Managers, Deposit Approvers,
Withdrawal Approvers, VIP Plan Managers, Reward Processors, Support Agents,
Notification Managers, Settings Managers**. Superusers bypass group checks;
regular staff need the group for each dangerous action.

## Routes

```
GET  /api/admin/dashboard/?range=today|7d|30d|all|custom&from&to
GET  /api/admin/users/?search&status&page        GET /api/admin/users/<user_id>/
POST /api/admin/users/<user_id>/status/          {action: activate|suspend|ban, reason}
GET  /api/admin/users/<user_id>/history/?type=deposits|withdrawals|vip|rewards|commissions|support|logins|audit

GET  /api/admin/deposits/?status=...             (Section 6 filters reused)
GET  /api/admin/deposits/<id>/                   POST .../approve/  POST .../reject/
GET  /api/admin/withdrawals/?status=...          GET /api/admin/withdrawals/<id>/
POST /api/admin/withdrawals/<id>/approve|reject|processing|complete|fail/

GET/POST /api/admin/vip-plans/                  PATCH/DELETE /api/admin/vip-plans/<id>/
GET  /api/admin/vip-purchases/                  GET /api/admin/rewards/
POST /api/admin/rewards/process/                POST /api/admin/rewards/<id>/retry/
GET  /api/admin/transactions/                   GET /api/admin/referrals/
GET  /api/admin/commissions/                    GET /api/admin/support/
GET  /api/admin/support/<conversation_id>/      POST .../messages/   POST .../status/
GET  /api/admin/notifications/                  POST /api/admin/notifications/broadcast/
GET  /api/admin/audit-logs/                     GET/PATCH /api/admin/settings/
```

## Financial safety (§50–51, §80)

- **No balance editing exists.** Wallet values are read-only everywhere; the
  user-detail page states this explicitly. There is no generic "edit balance"
  endpoint in the codebase.
- Deposits approve/reject through the Section 6 service; withdrawals move
  through the Section 10 state machine (`lock → release/finalize`) — one
  credit/release per action, idempotent on repeat.
- VIP plan edits never touch purchases: every purchase keeps its snapshot
  (verified live: plan 10/15 → 20/30 while purchase stayed 10/15/0.25).
- `rewards/process` and `rewards/<id>/retry` call the same idempotent reward
  service as Celery Beat.
- Completion never fabricates a `transaction_hash`; the field stays empty
  unless a real hash is supplied.

## Settings (§56–63)

Backed by `SiteSetting`. Seeded via `seed_platform_settings` so the values the
withdrawal/referral engines actually read are visible and editable. Every
PATCH is audited (`admin.setting`, old → new) and invalidates the matching
config cache so changes apply immediately. Secrets never live here.

## Demo/test transparency (§85)

- Dashboard financial cards are grouped under an explicit
  "DEMO/TEST FINANCIAL METRICS — NOT REAL REVENUE OR RETURNS" banner.
- `SimulatedWithdrawal` rows are never mixed into `Withdrawal` or ledger data.

## Frontend (`frontend/src`)

- `layouts/AdminLayout.tsx` — header + responsive sidebar/drawer (14 sections).
- `routes/adminRoutes.tsx` — lazy-loaded route tree behind a staff gate.
- `components/admin/AdminTable.tsx` — one reusable table (server pagination,
  server search, filters, loading/empty/error states, mobile card layout).
- `pages/admin/*` — Dashboard, Users, UserDetail, Deposits, Withdrawals,
  VIPPlans, VIPPurchases, Rewards, Referrals, Commissions, Support,
  SupportConversation, Transactions, Notifications, AuditLogs, Settings.
- All dangerous actions go through confirmation modals with context; busy
  states disable duplicate submissions.

## Testing

```bash
# backend (351 tests incl. 47 admin tests)
python manage.py test

# frontend typecheck + build
cd frontend && npx tsc --noEmit && npm run build
```

Admin tests cover: auth (401/403/staff-only), IDOR-safe lookups, mass
assignment rejection (`is_staff`/`is_superuser` ignored), suspension audit +
notification, deposit approve idempotency (single credit), withdrawal state
transitions, VIP snapshot preservation, permission-group enforcement, settings
validation + audit, and dashboard aggregation sanity.

## Live-verified (browser)

Dashboard stats + range filter, user search/filter/suspend/activate (audit +
notification confirmed in DB), deposit approve → wallet credited exactly once
(idempotent on repeat), withdrawal approve→processing→complete (ledger: one
LOCK pair + one finalize debit, no fabricated hash), reject → funds released,
staff support reply → user notification, resolve transition, settings edit →
audited + instantly live, VIP plan edit → snapshots preserved, reward cycle
processed (7 credited, 0 failed), mobile drawer layout.
