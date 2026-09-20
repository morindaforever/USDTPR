/** Admin panel types (Section 12). */

export interface AdminDashboard {
  range: string;
  total_users: number;
  active_users: number;
  staff_users: number;
  pending: {
    pending_deposits: number;
    pending_withdrawals: number;
    open_support: number;
    active_vip_purchases: number;
  };
  financial_metrics: {
    label: string;
    deposits_submitted: { count: number; amount: string };
    withdrawals_requested: { count: number; amount: string };
    vip_purchases: { count: number; investment: string };
    rewards_credited: { count: number; amount: string };
    commissions_credited: { count: number; amount: string };
  };
  registrations: Array<{ date: string; count: number }>;
  permission_groups: string[];
  recent_users: AdminUserRow[];
}

export interface AdminUserRow {
  user_id: string;
  full_name: string;
  email: string;
  phone: string;
  account_status: 'ACTIVE' | 'SUSPENDED' | 'BANNED';
  is_staff: boolean;
  created_at: string;
}

export interface AdminUserDetail extends AdminUserRow {
  referral_code: string;
  last_login: string | null;
  wallet: {
    total_balance: string;
    deposit_balance: string;
    withdrawable_balance: string;
    pending_balance: string;
    locked_balance: string;
    bonus_balance: string;
  };
  direct_referrals_count: number;
}

export interface AdminDepositRow {
  deposit_id: string;
  user_id: string;
  user_email?: string;
  network: string;
  network_name?: string;
  amount: string;
  tx_hash?: string;
  order_id?: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED';
  created_at: string;
  reviewed_at?: string | null;
  reviewer_email?: string | null;
  admin_note?: string;
  deposit_address?: string;
  has_screenshot?: boolean;
  /** MANUAL_VERIFICATION (default) or ON_CHAIN_VERIFIED (real provider ran). */
  verification_status?: 'MANUAL_VERIFICATION' | 'ON_CHAIN_VERIFIED';
}

/** Network configuration row (GET/PATCH /api/admin-panel/networks/). */
export interface AdminNetworkRow {
  id: number;
  code: string;
  name: string;
  asset: string;
  is_active: boolean;
  current_address: string | null;
  contract_address: string;
  min_deposit: string | null;
  min_withdrawal: string | null;
  withdrawal_fee: string | null;
  withdrawal_fee_is_percent: boolean | null;
  network_warning: string;
  instructions: string;
}

export interface AdminWithdrawalRow {
  withdrawal_id: string;
  user_id: string;
  user_email: string;
  network: string;
  wallet_address: string;
  amount: string;
  fee_amount: string;
  net_amount: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  created_at: string;
  tx_hash: string;
  rejection_reason: string;
  has_qr_image?: boolean;
}

export interface AdminVipPlan {
  id: number;
  name: string;
  plan_number: number | string;
  investment_amount: string;
  target_amount: string;
  daily_rate: string;
  is_active: boolean;
  sort_order: number;
}

export interface AdminVipPurchase {
  purchase_id: string;
  user_id: string;
  user_email: string;
  plan_name_snapshot: string;
  investment_amount: string;
  target_amount: string;
  daily_rate_snapshot: string;
  rewarded_amount: string;
  remaining_amount: string;
  status: string;
  started_at: string | null;
  created_at: string;
}

export interface AdminReward {
  reward_id: string;
  user_id: string;
  user_email: string;
  purchase_id: string;
  reward_date: string;
  calculated_amount: string;
  credited_amount: string;
  status: string;
  error_info: string;
  created_at: string;
}

export interface AdminReferralRow {
  id: number;
  referrer_id: string;
  referrer_email: string;
  referred_id: string;
  referred_email: string;
  status: string;
  created_at: string;
}

export interface AdminCommissionRow {
  commission_id: string;
  beneficiary_id: string;
  beneficiary_email: string;
  source_user_id: string;
  level: number;
  commission_rate: string;
  source_reward_amount: string;
  commission_amount: string;
  status: string;
  created_at: string;
}

export interface AdminSupportRow {
  conversation_id: string;
  user_id: string;
  user_email: string;
  subject: string;
  status: 'OPEN' | 'IN_PROGRESS' | 'RESOLVED' | 'CLOSED';
  priority: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview: string;
}

export interface AdminSupportMessage {
  id: number;
  sender_id: string;
  sender_type: 'user' | 'support';
  message: string;
  created_at: string;
}

export interface AdminSupportDetail extends AdminSupportRow {
  closed_at: string | null;
  messages: AdminSupportMessage[];
}

export interface AdminTransaction {
  transaction_id: string;
  user_id: string;
  user_email: string;
  transaction_type: string;
  direction: 'CREDIT' | 'DEBIT';
  balance_type: string;
  amount: string;
  status: string;
  reference_type: string;
  reference_id: string;
  description: string;
  created_at: string;
}

export interface AdminNotification {
  id: number;
  user_id: string;
  notification_type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface AdminAuditLog {
  id: number;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  target_type: string;
  target_id: string;
  description: string;
  ip_address: string | null;
  created_at: string;
}

export interface AdminSetting {
  key: string;
  value: string;
  value_type: 'string' | 'integer' | 'decimal' | 'boolean' | 'json';
  description: string;
}
