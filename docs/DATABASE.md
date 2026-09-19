# Database Reference (Section 2)

Map of all models, their business IDs, and the financial invariants baked
into the schema. Later sections must respect these invariants.

## Model map

| App | Models | Business ID |
| --- | --- | --- |
| accounts | `User` (AUTH_USER_MODEL) | `USR000001` |
| wallet | `Wallet`, `WalletTransaction`, `Network`, `DepositAddress` | `TXN00000001` |
| deposits | `Deposit` | `DEP00000001` |
| withdrawals | `Withdrawal`, `WithdrawalRule`, `SimulatedWithdrawal` (demo-only) | `WDR00000001` |
| vip | `VIPPlan`, `VIPPurchase`, `VIPReward` | `VIP00000001`, `REW00000001` |
| referrals | `Referral`, `ReferralCommission` | `COM00000001` |
| support | `SupportConversation`, `SupportMessage` | `SUP00000001` |
| notifications | `Notification` | — |
| core | `AuditLog`, `SiteSetting`, `CompanyValuation`, `HumanIDCounter` | — |

## Financial invariants

1. **Money is `Decimal(24, 8)`** via `money_field()` — never floats.
2. **Balances live on `Wallet`** (six buckets, all `>= 0` enforced by DB
   constraints); **the ledger (`WalletTransaction`) explains every change**.
3. **Ledger rows are append-only.** Reversals are new opposite rows
   referencing the original via `reference_type`/`reference_id`.
4. **Idempotency**: `WalletTransaction.idempotency_key` (unique, nullable)
   plus structural uniqueness:
   - `VIPReward` unique on (`vip_purchase`, `reward_date`)
   - `ReferralCommission` 1:1 with `Deposit`
   - `DepositAddress` only one active per (network, asset)
5. **Business IDs** are minted by `HumanIDField` from a serialized counter
   (`select_for_update`); the unique index is the race-proof guarantee.
6. **Snapshots**: `VIPPurchase` copies plan terms at purchase time; admin
   plan edits never rewrite existing purchases. Deposits keep the deposit
   address used at submission.
7. **Self-referral** is blocked at both model-validation and DB constraint
   level (`referral_no_self_reference`); a user has at most one referrer.
8. **Demo data is segregated**: `SimulatedWithdrawal` is a separate table
   (no user FK), `CompanyValuation.is_demo` marks demo series. Neither may
   ever be mixed into real financial tables.

## Withdrawal rules (seeded)

| Amount | Required plan |
| --- | --- |
| ≤ 100 | VIP 1 |
| ≤ 500 | VIP 3 |
| ≤ 800 | VIP 6 |
| > 800 | VIP 7 |

Seeded by `python manage.py seed_demo_data` (idempotent), along with
networks (BSC, TRX, ETH, POL, SOL, TON) and VIP plans (WELCOME + VIP 1–7).
These are development/demo values, not product terms.

## Admin

All models are registered with search/filters/read-only timestamps.
`AuditLog` and `HumanIDCounter` are read-only by design. Dev superuser
credentials are local-only (created via `createsuperuser`).
