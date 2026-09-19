/**
 * Shared application types.
 *
 * Domain models (users, wallets, transactions, …) are added by their
 * respective sections. Keep only cross-cutting types here.
 */

/** Normalized error shape produced by the API client. */
export interface ApiError {
  /** HTTP status code, or null when the request never reached the server. */
  status: number | null;
  /** Human-readable message suitable for display in the UI. */
  message: string;
  /** Raw error payload from the backend, when available. */
  detail?: unknown;
}

/** Envelope for DRF paginated list responses. */
export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/** Standard success envelope used by the backend. */
export interface ApiEnvelope<T = unknown> {
  success: boolean;
  message: string;
  data?: T;
  errors?: Record<string, string[]>;
}

/** Shape returned by GET /api/health/. */
export interface HealthStatus {
  status: 'ok' | 'error';
  services?: Record<string, string>;
}

/** Wallet buckets returned by GET /api/wallet/summary/ (Decimal strings). */
export interface WalletSummary {
  total_balance: string;
  deposit_balance: string;
  withdrawable_balance: string;
  pending_balance: string;
  locked_balance: string;
  bonus_balance: string;
}

/** One ledger row from GET /api/wallet/transactions/. */
export interface WalletTransaction {
  transaction_id: string;
  type: string;
  direction: 'CREDIT' | 'DEBIT';
  amount: string;
  balance_type: string;
  status: 'PENDING' | 'COMPLETED' | 'REVERSED' | 'FAILED';
  description: string;
  reference_type: string;
  reference_id: string;
  created_at: string;
}

/** Pagination metadata attached to list responses. */
export interface PaginationMeta {
  page: number;
  page_size: number;
  count: number;
  pages: number;
}

/** Envelope for paginated wallet history responses. */
export interface PaginatedEnvelope<T> extends ApiEnvelope<T[]> {
  pagination?: PaginationMeta;
}

/** Query filters for the transaction history endpoint. */
export interface TransactionFilters {
  type?: string;
  status?: string;
  direction?: string;
  date_from?: string;
  date_to?: string;
  /** §23: free-text search over id/description/reference (backend-safe). */
  search?: string;
  page?: number;
  page_size?: number;
}

/** One notification row from GET /api/notifications/ (Section 13). */
export interface AppNotification {
  id: number;
  type: string;
  title: string;
  message: string;
  related_type: string;
  related_id: string;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

/** Filters for the notification list endpoint. */
export interface NotificationFilters {
  type?: string;
  is_read?: boolean | '';
  page?: number;
  page_size?: number;
}

/** Active VIP purchase snapshot from GET /api/vip/current/. */
export interface CurrentPlan {
  purchase_id: string;
  plan_name_snapshot: string;
  investment_amount: string;
  target_amount: string;
  daily_rate_snapshot: string;
  amount_received: string;
  status: 'PENDING' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
  started_at: string;
  is_welcome_plan: boolean;
  /** Section 8 progress — backend-computed (present when a plan exists). */
  rewarded_amount?: string;
  remaining_amount?: string;
  progress_percent?: string;
  next_reward_cycle?: string;
  /** ISO datetime of the next scheduled reward-engine run (Celery beat). */
  next_reward_at?: string;
}

/** VIP plan from GET /api/vip/plans/ (Decimal strings from the backend). */
export interface VipPlan {
  id: number;
  plan_number: number;
  name: string;
  investment_amount: string;
  target_amount: string;
  daily_rate: string;
  daily_rate_percent: string;
  profit_amount: string;
  is_active: boolean;
}

/** VIP purchase row from the purchase/history endpoints. */
export interface VipPurchase {
  purchase_id: string;
  plan_name: string;
  investment_amount: string;
  target_amount: string;
  daily_rate: string;
  daily_rate_percent: string;
  amount_received: string;
  status: 'PENDING' | 'ACTIVE' | 'COMPLETED' | 'CANCELLED';
  started_at: string | null;
  completed_at?: string | null;
  created_at: string;
  /** Progress fields (present on /vip/active responses, Section 8). */
  rewarded_amount?: string;
  remaining_amount?: string;
  progress_percent?: string;
  next_reward_cycle?: string;
}

/** Server-computed confirmation data for a plan purchase. */
export interface PlanPurchaseSummary {
  plan: VipPlan;
  available_balance: string;
  balance_after_purchase: string;
  sufficient: boolean;
}

/** Backend-computed reward progress for an active/completed purchase. */
export interface VipPurchaseProgress {
  rewarded_amount: string;
  remaining_amount: string;
  progress_percent: string;
  next_reward_cycle: string;
  /** ISO datetime of the next scheduled reward-engine run (Celery beat). */
  next_reward_at?: string;
}

/** One reward cycle from GET /api/vip/rewards/. */
export interface VipReward {
  reward_id: string;
  purchase_id: string;
  plan_name: string;
  reward_date: string;
  calculated_amount: string;
  credited_amount: string;
  status: 'PENDING' | 'COMPLETED' | 'FAILED' | 'REVERSED';
  transaction_id: string | null;
  created_at: string;
  processed_at: string | null;
}

/** Successful (or replayed) purchase response. */
export interface PurchaseResponse {
  purchase: VipPurchase;
  remaining_balance: string;
  already_existed: boolean;
}

/** Referral summary from GET /api/referrals/summary/ (Section 9). */
export interface ReferralSummary {
  referral_code: string;
  referral_link: string;
  direct_referrals: number;
  total_team: number;
  active_team: number;
  level_counts: Record<string, number>;
  commission_totals: {
    total: string;
    this_cycle: string;
    by_level: Record<string, string>;
  };
  max_level: number;
  commission_rates: Record<string, string>;
}

/** One team member from /api/referrals/team/ or /direct/. */
export interface TeamMember {
  user_id: string;
  full_name: string;
  level: number;
  status: 'ACTIVE' | 'SUSPENDED' | 'BANNED';
  joined_at: string;
}

/** One referral commission from GET /api/referrals/commissions/. */
export interface ReferralCommission {
  commission_id: string;
  source_user_id: string;
  level: number;
  reward_id: string;
  source_reward_amount: string;
  commission_rate_percent: string;
  commission_amount: string;
  status: 'PENDING' | 'CREDITED' | 'FAILED' | 'REVERSED';
  cycle_date: string | null;
  created_at: string;
  processed_at: string | null;
  transaction_id: string | null;
}

// ---------------------------------------------------------------------------
// Withdrawals (Section 10)
// ---------------------------------------------------------------------------

/** Active network from GET /api/withdrawals/networks/. */
/** Active deposit network from GET /api/deposits/networks/. */
export interface DepositNetwork {
  code: string;
  name: string;
  asset: string;
}

/** Deposit address + server-rendered QR from GET /api/deposits/address/. */
export interface DepositAddress {
  network: string;
  asset: string;
  address: string;
  qr_code: string;
}

/** One deposit row from GET /api/deposits/. */
export interface Deposit {
  deposit_id: string;
  network: string;
  network_name: string;
  asset: string;
  amount: string;
  tx_hash: string;
  order_id: string;
  deposit_address: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  admin_note: string;
  submitted_at: string;
  approved_at: string | null;
  rejected_at: string | null;
  created_at: string;
}

export interface WithdrawalNetwork {
  code: string;
  name: string;
  asset: string;
  /** Format guidance only — the backend does format checks, not on-chain. */
  address_hint: string;
}

/** Public withdrawal rules from GET /api/withdrawals/rules/ (§46). */
export interface WithdrawalRules {
  minimum_amount: string;
  fee_type: 'FIXED' | 'PERCENT' | 'ZERO';
  fee_amount: string;
  fee_unit: string;
}

/** Balances for /withdraw — every value is backend-computed (§6, §41). */
export interface WithdrawalSummary {
  withdrawable_balance: string;
  locked_balance: string;
  pending_withdrawals: string;
}

/** Informational quote from POST /api/withdrawals/quote/ (§47). */
export interface WithdrawalQuote {
  amount: string;
  fee: string;
  net_amount: string;
  minimum_amount: string;
  fee_type: string;
}

/** Withdrawal row from the list endpoint — address is masked (§40). */
export interface Withdrawal {
  withdrawal_id: string;
  network: string;
  network_name: string;
  masked_address: string;
  amount: string;
  fee_amount: string;
  net_amount: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  tx_hash: string;
  created_at: string;
  completed_at: string | null;
}

/** Detail adds the full destination, reason, and timestamps (§39, §44). */
export interface WithdrawalDetail extends Withdrawal {
  destination_address: string;
  rejection_reason: string;
  approved_at: string | null;
  rejected_at: string | null;
  processing_at: string | null;
  failed_at: string | null;
}

/** Successful (or idempotently replayed) submission response. */
export interface WithdrawalCreateResponse {
  withdrawal: WithdrawalDetail;
  already_existed: boolean;
}

// ---------------------------------------------------------------------------
// Account & Support (Section 11)
// ---------------------------------------------------------------------------

/** Safe activity entry from GET /api/account/activity/ (§19). */
export interface AccountActivityEntry {
  type: 'login' | 'profile_update' | 'deposit' | 'withdrawal' | 'vip_purchase' | 'reward';
  title: string;
  detail: string;
  occurred_at: string;
}

export type SupportStatus = 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';

/** Thread message — plain text; sender shown as a role, not an account. */
export interface SupportMessage {
  id: number;
  sender_type: 'user' | 'support';
  message: string;
  created_at: string;
}

/** Conversation row from the list endpoint (§28). */
export interface SupportConversation {
  conversation_id: string;
  subject: string;
  status: SupportStatus;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  last_message_preview: string;
}

/** Detail payload with the capped message thread (§34). */
export interface SupportConversationDetail extends SupportConversation {
  closed_at: string | null;
  messages: SupportMessage[];
}
