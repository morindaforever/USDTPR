import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowUpFromLine,
  BadgeCheck,
  Check,
  Copy,
  Crown,
  KeyRound,
  Link2,
  LifeBuoy,
  LogOut,
  MessageCircleQuestion,
  Pencil,
  Shield,
  Wallet,
} from 'lucide-react';
import { Badge, Button, Card, PageContainer } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { useAuth } from '@/context/AuthContext';
import { accountService } from '@/services/accountService';
import { formatUsdt, formatDate } from '@/utils/format';
import type { AccountActivityEntry } from '@/types';

/**
 * Account page (Section 11): profile view/edit, referral info, security,
 * curated activity feed, and links into the existing wallet/VIP/support
 * surfaces. Protected fields (user_id, status, referral code) render
 * read-only — the backend ignores them in PATCH payloads anyway (§77).
 */
export function AccountPage() {
  const { currentUser, refreshUser, logout } = useAuth();
  const navigate = useNavigate();

  // Profile editing state
  const [editing, setEditing] = useState(false);
  const [fullName, setFullName] = useState('');
  const [phone, setPhone] = useState('');
  const [saving, setSaving] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [profileSaved, setProfileSaved] = useState(false);

  const activityQuery = useDashboardData<AccountActivityEntry[]>(
    () => accountService.activity(),
    { enabled: currentUser !== null },
  );

  // Referral link built from the Section 9 backend base URL convention.
  const [referralLink, setReferralLink] = useState('');
  useEffect(() => {
    const base = (import.meta.env.VITE_PUBLIC_APP_URL as string | undefined)?.replace(/\/$/, '')
      ?? window.location.origin;
    if (currentUser) setReferralLink(`${base}/signup?ref=${encodeURIComponent(currentUser.referral_code)}`);
  }, [currentUser]);

  // Copied feedback (code + link)
  const [copiedField, setCopiedField] = useState<string | null>(null);
  const copy = useCallback(async (field: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(field);
      window.setTimeout(() => setCopiedField(null), 1500);
    } catch {
      // Clipboard unavailable — non-critical.
    }
  }, []);

  const startEditing = () => {
    if (!currentUser) return;
    setFullName(currentUser.full_name);
    setPhone(currentUser.phone);
    setProfileError(null);
    setProfileSaved(false);
    setEditing(true);
  };

  const saveProfile = async () => {
    setSaving(true);
    setProfileError(null);
    try {
      await accountService.updateProfile({ full_name: fullName.trim(), phone: phone.trim() });
      await refreshUser();
      setEditing(false);
      setProfileSaved(true);
      window.setTimeout(() => setProfileSaved(false), 2500);
      activityQuery.retry();
    } catch (err: unknown) {
      setProfileError(err instanceof Error ? err.message : 'Unable to update the profile.');
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
    } finally {
      navigate('/login', { replace: true });
    }
  };

  if (!currentUser) return null;

  return (
    <PageContainer
      title="My Account"
      subtitle={`Welcome back, ${currentUser.full_name || 'there'}`}
    >
      <div className="space-y-5">
        {/* Profile card (§5) */}
        <Card>
          <div className="p-5">
            <div className="flex items-center gap-4">
              <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-brand-50 font-display text-lg font-bold text-brand-700">
                {currentUser.full_name?.trim()?.charAt(0).toUpperCase() || '?'}
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-surface-900">
                  {currentUser.full_name || 'Unnamed user'}
                </p>
                <p className="truncate text-xs text-surface-500">{currentUser.email}</p>
              </div>
              {currentUser.account_status === 'ACTIVE' ? (
                <Badge tone="success">
                  <BadgeCheck className="h-3 w-3" aria-hidden /> Active
                </Badge>
              ) : (
                <Badge tone="danger">{currentUser.account_status.toLowerCase()}</Badge>
              )}
            </div>

            <dl className="mt-4 space-y-2.5 border-t border-surface-100 pt-4 text-sm">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-surface-500">User ID</dt>
                <dd className="font-mono font-semibold text-surface-900">{currentUser.user_id}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-surface-500">Full Name</dt>
                <dd className="font-medium text-surface-900">{currentUser.full_name || '—'}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-surface-500">Phone</dt>
                <dd className="font-medium tabular-nums text-surface-900">{currentUser.phone}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-surface-500">Status</dt>
                <dd className="font-medium text-surface-900">{currentUser.account_status}</dd>
              </div>
            </dl>

            {profileSaved && (
              <p className="mt-3 rounded-xl bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">
                Profile updated.
              </p>
            )}
            {profileError && (
              <p className="mt-3 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700">{profileError}</p>
            )}

            {editing ? (
              <div className="mt-4 space-y-3">
                <div>
                  <label htmlFor="edit-full-name" className="mb-1 block text-xs font-medium text-surface-600">
                    Full Name
                  </label>
                  <input
                    id="edit-full-name"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    maxLength={120}
                    className="w-full rounded-xl border border-surface-200 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  />
                </div>
                <div>
                  <label htmlFor="edit-phone" className="mb-1 block text-xs font-medium text-surface-600">
                    Phone
                  </label>
                  <input
                    id="edit-phone"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    inputMode="tel"
                    maxLength={20}
                    className="w-full rounded-xl border border-surface-200 px-3 py-2.5 text-sm tabular-nums focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                  />
                  <p className="mt-1 text-[11px] text-surface-400">
                    Email is read-only. Contact support to change it.
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button variant="secondary" fullWidth onClick={() => setEditing(false)} disabled={saving}>
                    Cancel
                  </Button>
                  <Button fullWidth isLoading={saving} onClick={() => void saveProfile()}>
                    Save Changes
                  </Button>
                </div>
              </div>
            ) : (
              <Button variant="outline" fullWidth className="mt-4" leftIcon={<Pencil className="h-4 w-4" />} onClick={startEditing}>
                Edit Profile
              </Button>
            )}
          </div>
        </Card>

        {/* Referral information (§11) — reuses the Section 9 code */}
        <section aria-labelledby="referral-heading">
          <h2 id="referral-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Referral Information
          </h2>
          <Card>
            <div className="space-y-3 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-surface-400">
                    Referral Code
                  </p>
                  <p className="truncate font-mono text-sm font-semibold text-surface-900">
                    {currentUser.referral_code}
                  </p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void copy('code', currentUser.referral_code)}
                  leftIcon={copiedField === 'code' ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
                >
                  {copiedField === 'code' ? 'Copied' : 'Copy Code'}
                </Button>
              </div>
              <div className="flex items-center justify-between gap-3 border-t border-surface-100 pt-3">
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-surface-400">
                    Referral Link
                  </p>
                  <p className="truncate font-mono text-xs text-surface-600">{referralLink}</p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void copy('link', referralLink)}
                  leftIcon={copiedField === 'link' ? <Check className="h-3.5 w-3.5" /> : <Link2 className="h-3.5 w-3.5" />}
                >
                  {copiedField === 'link' ? 'Copied' : 'Copy Link'}
                </Button>
              </div>
            </div>
          </Card>
        </section>

        {/* Activity (§18–§19) — curated safe feed */}
        <section aria-labelledby="activity-heading">
          <h2 id="activity-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Recent Activity
          </h2>
          <Card>
            {activityQuery.isLoading ? (
              <div className="space-y-3 p-4">
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
                <Skeleton className="h-10 w-full" />
              </div>
            ) : activityQuery.error ? (
              <p className="p-4 text-sm text-surface-500">Unable to load activity.</p>
            ) : (activityQuery.data ?? []).length === 0 ? (
              <p className="p-4 text-sm text-surface-500">No activity yet.</p>
            ) : (
              <ul className="divide-y divide-surface-100">
                {(activityQuery.data ?? []).slice(0, 10).map((entry, index) => {
                  const MONEY_TYPES = new Set(['deposit', 'withdrawal', 'vip_purchase', 'reward']);
                  return (
                    <li key={`${entry.type}-${entry.occurred_at}-${index}`} className="flex items-center justify-between gap-3 px-4 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-surface-800">{entry.title}</p>
                        {entry.detail && MONEY_TYPES.has(entry.type) && (
                          <p className="truncate text-xs tabular-nums text-surface-400">
                            {formatUsdt(entry.detail)} USDT
                          </p>
                        )}
                      </div>
                      <span className="shrink-0 text-xs text-surface-400">{formatDate(entry.occurred_at)}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </section>

        {/* Quick links into existing financial surfaces (§64) */}
        <section aria-labelledby="links-heading">
          <h2 id="links-heading" className="mb-3 text-sm font-semibold text-surface-900">
            History &amp; Records
          </h2>
          <Card>
            <ul className="divide-y divide-surface-100">
              {[
                { icon: Wallet, label: 'Balances & transactions', note: 'Full ledger history', to: '/wallet' },
                { icon: ArrowUpFromLine, label: 'Withdrawals', note: 'Requests and review status', to: '/withdraw' },
                { icon: Crown, label: 'VIP plans', note: 'Plans, rewards, purchases', to: '/vip' },
              ].map(({ icon: Icon, label, note, to }) => (
                <li key={to}>
                  <button
                    type="button"
                    onClick={() => navigate(to)}
                    className="flex w-full items-center justify-between px-4 py-3.5 text-left transition-colors hover:bg-surface-50"
                  >
                    <span className="flex items-center gap-3">
                      <Icon className="h-4 w-4 text-surface-400" aria-hidden />
                      <span>
                        <span className="block text-sm font-medium text-surface-700">{label}</span>
                        <span className="block text-xs text-surface-400">{note}</span>
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </section>

        {/* Security (§13) */}
        <section aria-labelledby="security-heading">
          <h2 id="security-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Security
          </h2>
          <Card>
            <ul className="divide-y divide-surface-100">
              <li>
                <button
                  type="button"
                  onClick={() => navigate('/account/change-password')}
                  className="flex w-full items-center justify-between px-4 py-3.5 text-left transition-colors hover:bg-surface-50"
                >
                  <span className="flex items-center gap-3">
                    <KeyRound className="h-4 w-4 text-surface-400" aria-hidden />
                    <span>
                      <span className="block text-sm font-medium text-surface-700">Change password</span>
                      <span className="block text-xs text-surface-400">
                        All other sessions are signed out after a change
                      </span>
                    </span>
                  </span>
                </button>
              </li>
              <li>
                <button
                  type="button"
                  onClick={() => navigate('/forgot-password')}
                  className="flex w-full items-center justify-between px-4 py-3.5 text-left transition-colors hover:bg-surface-50"
                >
                  <span className="flex items-center gap-3">
                    <Shield className="h-4 w-4 text-surface-400" aria-hidden />
                    <span className="text-sm font-medium text-surface-700">Forgot password (reset by email)</span>
                  </span>
                </button>
              </li>
            </ul>
          </Card>
        </section>

        {/* Support (§21) */}
        <section aria-labelledby="support-heading">
          <h2 id="support-heading" className="mb-3 text-sm font-semibold text-surface-900">
            Support
          </h2>
          <Card>
            <ul className="divide-y divide-surface-100">
              <li>
                <button
                  type="button"
                  onClick={() => navigate('/support')}
                  className="flex w-full items-center justify-between px-4 py-3.5 text-left transition-colors hover:bg-surface-50"
                >
                  <span className="flex items-center gap-3">
                    <LifeBuoy className="h-4 w-4 text-surface-400" aria-hidden />
                    <span>
                      <span className="block text-sm font-medium text-surface-700">My support conversations</span>
                      <span className="block text-xs text-surface-400">Open a ticket or follow up</span>
                    </span>
                  </span>
                </button>
              </li>
              <li>
                <button
                  type="button"
                  onClick={() => navigate('/help')}
                  className="flex w-full items-center justify-between px-4 py-3.5 text-left transition-colors hover:bg-surface-50"
                >
                  <span className="flex items-center gap-3">
                    <MessageCircleQuestion className="h-4 w-4 text-surface-400" aria-hidden />
                    <span className="text-sm font-medium text-surface-700">Help center &amp; FAQ</span>
                  </span>
                </button>
              </li>
            </ul>
          </Card>
        </section>

        <Button
          variant="outline"
          fullWidth
          onClick={() => void handleLogout()}
          leftIcon={<LogOut className="h-4 w-4" />}
        >
          Log out
        </Button>
      </div>
    </PageContainer>
  );
}
