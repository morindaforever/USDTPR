# Withdrawal System (Section 10)

User-facing withdrawal requests with admin review. **No real blockchain
transfers are performed** — the workflow is manual/admin processing in
demo/test mode. Nothing in this app fabricates transaction hashes or claims
an on-chain payout that did not happen.

## Flow

```text
/withdraw (auth required)
   → select network → enter destination address → enter amount
   → backend quote (fee + net, informational only)
   → confirm modal → POST /api/withdrawals/
        ↓
Withdrawal Service (apps/withdrawals/services.py)
        ↓  validate account/network/address/amount/minimum
Wallet Service .lock()          (withdrawable → locked, ledger rows)
        ↓
Withdrawal created as PENDING   (fee snapshot frozen)
        ↓
Admin review: approve / reject  (reject ⇒ Wallet Service .release_lock())
        ↓  APPROVED → PROCESSING (no wallet movement)
        ↓  PROCESSING → COMPLETED (Wallet Service .finalize_locked())
                     → FAILED     (Wallet Service .release_lock())
```

## Status machine

| Transition | Guard | Wallet effect |
| --- | --- | --- |
| → `PENDING` | submission validations | lock funds |
| `PENDING → APPROVED` | admin | none (funds stay locked) |
| `PENDING → REJECTED` | admin + reason | release locked funds |
| `APPROVED → PROCESSING` | admin | none |
| `PROCESSING → COMPLETED` | admin (+ payout reference) | finalize locked funds (paid out) |
| `PROCESSING → FAILED` | admin + reason | release locked funds |

Anything else is rejected (`Invalid status transition.`). Double
rejection/completion/failure is safe — the second call raises, the ledger is
never touched twice.

## Money handling

- **All balance movement goes through the Section 5 wallet service.** No view
  or serializer ever writes `Wallet` columns.
- **Fee snapshot:** `requested_amount`, `fee_amount`, `net_amount` are frozen
  on the withdrawal row at creation; later config changes never rewrite
  history. `net_amount < 0` is impossible (validated with `Decimal`).
- **Minimum & fee config** live in `apps/withdrawals/config.py`, sourced from
  the Section 2 `WithdrawalRule` model (fixed, percent, or zero fee).
- **Idempotency:** `idempotency_key` is unique per user. The same key returns
  the ORIGINAL withdrawal (201 first time, 200 replay) and locks funds at
  most once.
- **Concurrency:** wallet row is locked with `select_for_update` inside one
  transaction; two simultaneous requests for the same funds cannot both lock.

## Address validation (`address_validation.py`)

Network-aware **format validation only** — never claimed as on-chain proof:
BSC/ETH/POL `0x` + 40 hex (with EIP-55 optional checksum awareness), TRX `T` +
33 base58 with version-byte checksum, SOL base58 32–44, TON base64url 48.
The UI labels it "Format validation only".

## API

User (auth required, owner-scoped data only):

| Endpoint | Purpose |
| --- | --- |
| `GET /api/withdrawals/networks/` | active networks + address format hints |
| `GET /api/withdrawals/rules/` | public minimum + fee configuration |
| `GET /api/withdrawals/summary/` | withdrawable / locked / pending (backend-computed) |
| `POST /api/withdrawals/quote/` | informational fee/net quote |
| `POST /api/withdrawals/` | submit (network, destination_address, amount, idempotency_key) |
| `GET /api/withdrawals/` | paginated history (masked destination) |
| `GET /api/withdrawals/<withdrawal_id>/` | owner-only detail (full destination) |

Admin (staff-only, `/api/admin-panel/withdrawals/`): list queue, approve,
reject (reason required), start processing, complete (reference recorded but
never auto-generated), fail (releases funds).

Every transition writes an audit log and notifies the user.

## Demo / simulated activity

`SimulatedWithdrawal` (Section 2) still powers the dashboard's demo feed.
Those rows have no user FK and no balance effect and are labeled
"Demo / Simulated Activity" — they never mix with real withdrawal records.

## Reconciliation

`python manage.py reconcile_wallets` also validates, per user, that:

- locked balance equals the sum of open (`PENDING/APPROVED/PROCESSING`)
  withdrawal locks;
- completed withdrawals have exactly one finalize (locked DEBIT);
- rejected/failed withdrawals released their funds exactly once.

## Tests

`backend/apps/withdrawals/` — 48 tests: validation, fees, minimum,
idempotent replay, concurrency, full state machine, double transitions,
isolation, admin authorization, reconciliation invariants.
