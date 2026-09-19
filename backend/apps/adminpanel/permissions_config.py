"""Catalog of admin permission groups (Section 12 §65).

Single source of truth for ``bootstrap_admin_groups`` and the docs; views
reference these names via ``required_groups``.
"""

ADMIN_GROUPS = {
    'User Managers': 'Suspend/activate/ban users, view user details',
    'Deposit Approvers': 'Approve and reject deposits, manage deposit addresses',
    'Withdrawal Approvers': 'Approve/reject/process withdrawals',
    'Withdrawal Completers': 'Mark processed withdrawals completed or failed',
    'VIP Managers': 'Create and edit VIP plans',
    'Reward Processors': 'Trigger reward processing and retries',
    'Referral Managers': 'View referral tree and commissions, edit referral rates',
    'Support Agents': 'View and reply to support conversations',
    'Notification Managers': 'Send announcement notifications',
    'Settings Managers': 'Edit platform settings',
}
