import { lazy, Suspense, type ReactNode } from 'react';
import { Navigate, createBrowserRouter } from 'react-router-dom';
import { PublicLayout } from '@/layouts/PublicLayout';
import { DashboardLayout } from '@/layouts/DashboardLayout';
import { RequireAuth, RequireGuest } from '@/context/AuthContext';
import { Spinner } from '@/components/Spinner';
import { NotFoundPage } from '@/pages/NotFoundPage';
import AdminRoutes from '@/routes/adminRoutes';
import { LandingPage } from '@/pages/LandingPage';

/**
 * Route-level code splitting. The landing page is bundled eagerly so the
 * first paint is instant; everything else loads on demand.
 */
const LoginPage = lazy(() => import('@/pages/auth/LoginPage').then((m) => ({ default: m.LoginPage })));
const SignupPage = lazy(() => import('@/pages/auth/SignupPage').then((m) => ({ default: m.SignupPage })));
const ForgotPasswordPage = lazy(() =>
  import('@/pages/auth/ForgotPasswordPage').then((m) => ({ default: m.ForgotPasswordPage })),
);
const ResetPasswordPage = lazy(() =>
  import('@/pages/auth/ResetPasswordPage').then((m) => ({ default: m.ResetPasswordPage })),
);
const AboutPage = lazy(() => import('@/pages/AboutPage').then((m) => ({ default: m.AboutPage })));
const HelpPage = lazy(() => import('@/pages/HelpPage').then((m) => ({ default: m.HelpPage })));
const HomePage = lazy(() =>
  import('@/pages/dashboard/HomePage').then((m) => ({ default: m.HomePage })),
);
const VipPage = lazy(() =>
  import('@/pages/dashboard/VipPage').then((m) => ({ default: m.VipPage })),
);
const TeamPage = lazy(() =>
  import('@/pages/dashboard/TeamPage').then((m) => ({ default: m.TeamPage })),
);
const AccountPage = lazy(() =>
  import('@/pages/dashboard/AccountPage').then((m) => ({ default: m.AccountPage })),
);
const ChangePasswordPage = lazy(() =>
  import('@/pages/auth/ChangePasswordPage').then((m) => ({ default: m.ChangePasswordPage })),
);
const DepositPage = lazy(() =>
  import('@/pages/dashboard/DepositPage').then((m) => ({ default: m.DepositPage })),
);
const WithdrawPage = lazy(() =>
  import('@/pages/dashboard/WithdrawPage').then((m) => ({ default: m.WithdrawPage })),
);
const WalletPage = lazy(() =>
  import('@/pages/dashboard/WalletPage').then((m) => ({ default: m.WalletPage })),
);
const NotificationsPage = lazy(() =>
  import('@/pages/dashboard/NotificationsPage').then((m) => ({ default: m.NotificationsPage })),
);
const TransactionsPage = lazy(() =>
  import('@/pages/dashboard/TransactionsPage').then((m) => ({ default: m.TransactionsPage })),
);
const TransactionDetailPage = lazy(() =>
  import('@/pages/dashboard/TransactionDetailPage').then((m) => ({
    default: m.TransactionDetailPage,
  })),
);
const SupportPage = lazy(() =>
  import('@/pages/dashboard/SupportPage').then((m) => ({ default: m.SupportPage })),
);
const SupportConversationPage = lazy(() =>
  import('@/pages/dashboard/SupportConversationPage').then((m) => ({
    default: m.SupportConversationPage,
  })),
);

/** Suspense fallback for lazily loaded routes. */
function RouteFallback(): ReactNode {
  return (
    <div className="flex min-h-[50dvh] items-center justify-center">
      <Spinner size="lg" label="Loading page" />
    </div>
  );
}

/** Wrap lazy elements in Suspense with the standard fallback. */
function withSuspense(element: ReactNode): ReactNode {
  return <Suspense fallback={<RouteFallback />}>{element}</Suspense>;
}

/**
 * Application route tree.
 *
 * Dashboard routes are wrapped in RequireAuth (redirects to /login when
 * unauthenticated); auth screens use RequireGuest (redirects to /home when
 * already signed in).
 */
export const router = createBrowserRouter(
  [
    {
      element: <PublicLayout />,
      children: [
        { path: '/', element: <LandingPage /> },
        { path: '/login', element: withSuspense(<RequireGuest>{<LoginPage />}</RequireGuest>) },
        { path: '/signup', element: withSuspense(<RequireGuest>{<SignupPage />}</RequireGuest>) },
        {
          path: '/forgot-password',
          element: withSuspense(<RequireGuest>{<ForgotPasswordPage />}</RequireGuest>),
        },
        {
          path: '/reset-password/:token',
          element: withSuspense(<RequireGuest>{<ResetPasswordPage />}</RequireGuest>),
        },
        { path: '/about', element: withSuspense(<AboutPage />) },
        { path: '/help', element: withSuspense(<HelpPage />) },
      ],
    },
    {
      element: <DashboardLayout />,
      children: [
        { path: '/home', element: withSuspense(<RequireAuth>{<HomePage />}</RequireAuth>) },
        { path: '/vip', element: withSuspense(<RequireAuth>{<VipPage />}</RequireAuth>) },
        { path: '/team', element: withSuspense(<RequireAuth>{<TeamPage />}</RequireAuth>) },
        { path: '/account', element: withSuspense(<RequireAuth>{<AccountPage />}</RequireAuth>) },
        {
          path: '/account/change-password',
          element: withSuspense(<RequireAuth>{<ChangePasswordPage />}</RequireAuth>),
        },
        { path: '/deposit', element: withSuspense(<RequireAuth>{<DepositPage />}</RequireAuth>) },
        { path: '/withdraw', element: withSuspense(<RequireAuth>{<WithdrawPage />}</RequireAuth>) },
        { path: '/wallet', element: withSuspense(<RequireAuth>{<WalletPage />}</RequireAuth>) },
        {
          path: '/notifications',
          element: withSuspense(<RequireAuth>{<NotificationsPage />}</RequireAuth>),
        },
        {
          path: '/transactions',
          element: withSuspense(<RequireAuth>{<TransactionsPage />}</RequireAuth>),
        },
        {
          path: '/transactions/:transactionId',
          element: withSuspense(<RequireAuth>{<TransactionDetailPage />}</RequireAuth>),
        },
        { path: '/support', element: withSuspense(<RequireAuth>{<SupportPage />}</RequireAuth>) },
        {
          path: '/support/:conversationId',
          element: withSuspense(<RequireAuth>{<SupportConversationPage />}</RequireAuth>),
        },
      ],
    },
    {
      // NOTE: no admin guard yet — admin auth arrives in its own section.
      path: '/admin/*',
      element: withSuspense(<AdminRoutes />),
    },
    { path: '/dashboard', element: <Navigate to="/home" replace /> },
    { path: '*', element: <NotFoundPage /> },
  ],
  {
    future: {
      v7_relativeSplatPath: true,
    },
  },
);
