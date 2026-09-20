import { lazy, Suspense, type ReactNode } from 'react';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';
import AdminLayout from '@/layouts/AdminLayout';
import { useAuth } from '@/context/AuthContext';
import { Spinner } from '@/components/Spinner';

const AdminDashboardPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminDashboardPage')).AdminDashboardPage }));
const AdminUsersPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminUsersPage')).AdminUsersPage }));
const AdminUserDetailPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminUserDetailPage')).AdminUserDetailPage }));
const AdminDepositsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminDepositsPage')).AdminDepositsPage }));
const AdminDepositAddressesPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminDepositAddressesPage')).AdminDepositAddressesPage }));
const AdminWithdrawalsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminWithdrawalsPage')).AdminWithdrawalsPage }));
const AdminVipPlansPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminVipPlansPage')).AdminVipPlansPage }));
const AdminVipPurchasesPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminVipPurchasesPage')).AdminVipPurchasesPage }));
const AdminRewardsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminRewardsPage')).AdminRewardsPage }));
const AdminReferralsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminReferralsPage')).AdminReferralsPage }));
const AdminCommissionsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminCommissionsPage')).AdminCommissionsPage }));
const AdminSupportPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminSupportPage')).AdminSupportPage }));
const AdminSupportConversationPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminSupportConversationPage')).AdminSupportConversationPage }));
const AdminTransactionsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminTransactionsPage')).AdminTransactionsPage }));
const AdminNotificationsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminNotificationsPage')).AdminNotificationsPage }));
const AdminAuditLogsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminAuditLogsPage')).AdminAuditLogsPage }));
const AdminSettingsPage = lazy(async () => ({ default: (await import('@/pages/admin/AdminSettingsPage')).AdminSettingsPage }));

const suspense = (node: ReactNode) => (
  <Suspense fallback={<div className="flex min-h-[50vh] items-center justify-center"><Spinner size="lg" label="Loading" /></div>}>
    {node}
  </Suspense>
);

/**
 * Presentation-only staff gate (§3): the backend enforces IsAdminUser +
 * per-action group permissions on every /api/admin/* call regardless.
 */
function RequireAdmin() {
  const { currentUser, isLoading } = useAuth();
  if (isLoading) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-surface-950">
        <Spinner size="lg" label="Checking access" />
      </div>
    );
  }
  if (!currentUser) return <Navigate to="/login" replace />;
  if (!currentUser.is_staff) return <Navigate to="/home" replace />;
  return <Outlet />;
}

/** Section 12 admin route tree. */
export default function AdminRoutes() {
  return (
    <Routes>
      <Route element={<RequireAdmin />}>
        <Route element={<AdminLayout />}>
          <Route index element={suspense(<AdminDashboardPage />)} />
          <Route path="users" element={suspense(<AdminUsersPage />)} />
          <Route path="users/:userId" element={suspense(<AdminUserDetailPage />)} />
          <Route path="deposits" element={suspense(<AdminDepositsPage />)} />
          <Route path="deposit-addresses" element={suspense(<AdminDepositAddressesPage />)} />
          <Route path="withdrawals" element={suspense(<AdminWithdrawalsPage />)} />
          <Route path="vip-plans" element={suspense(<AdminVipPlansPage />)} />
          <Route path="vip-purchases" element={suspense(<AdminVipPurchasesPage />)} />
          <Route path="rewards" element={suspense(<AdminRewardsPage />)} />
          <Route path="referrals" element={suspense(<AdminReferralsPage />)} />
          <Route path="commissions" element={suspense(<AdminCommissionsPage />)} />
          <Route path="support" element={suspense(<AdminSupportPage />)} />
          <Route path="support/:conversationId" element={suspense(<AdminSupportConversationPage />)} />
          <Route path="transactions" element={suspense(<AdminTransactionsPage />)} />
          <Route path="notifications" element={suspense(<AdminNotificationsPage />)} />
          <Route path="audit-logs" element={suspense(<AdminAuditLogsPage />)} />
          <Route path="settings" element={suspense(<AdminSettingsPage />)} />
          <Route path="*" element={<Navigate to="/admin" replace />} />
        </Route>
      </Route>
    </Routes>
  );
}
