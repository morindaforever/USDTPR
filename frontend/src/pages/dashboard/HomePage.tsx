import { useCallback } from 'react';
import { MaintenanceBanner, PageContainer, TelegramCommunityCard } from '@/components';
import { useDashboardData } from '@/hooks';
import { useAuth } from '@/context/AuthContext';
import { walletService, vipService, referralService } from '@/services';
import {
  BalanceCard,
  CurrentPlanCard,
  EcosystemGrid,
  QuickActions,
  RecentNotifications,
  RecentTransactions,
  TeamSummaryCard,
} from '@/components/dashboard';
import type { CurrentPlan, ReferralSummary, WalletSummary } from '@/types';

/** First name for the welcome line; falls back to the full name. */
function firstName(fullName: string): string {
  return fullName.trim().split(/\s+/)[0] || fullName;
}

/**
 * Authenticated home dashboard. Pure composition + data wiring: every
 * section is a reusable component with its own loading/error/empty states,
 * so one failed request never breaks the whole page.
 */
export function HomePage() {
  const { currentUser } = useAuth();

  const walletFetcher = useCallback(() => walletService.summary(), []);
  const planFetcher = useCallback(() => vipService.currentPlan(), []);
  const teamFetcher = useCallback(() => referralService.summary(), []);

  const wallet = useDashboardData<WalletSummary>(walletFetcher);
  const plan = useDashboardData<CurrentPlan | null>(planFetcher);
  const team = useDashboardData<ReferralSummary>(teamFetcher);

  const displayName = currentUser ? firstName(currentUser.full_name) : 'there';

  return (
    <PageContainer
      title={`Welcome back, ${displayName} 👋`}
      subtitle="Your account at a glance."
    >
      <div className="space-y-6">
        {/* §37: backend-driven maintenance notice (admin-panel switch). */}
        <MaintenanceBanner />

        {/* Desktop: balance and plan side by side; mobile stacks them. */}
        <div className="grid gap-6 xl:grid-cols-[3fr_2fr]">
          <BalanceCard
            summary={wallet.data}
            isLoading={wallet.isLoading}
            error={wallet.error}
            onRetry={wallet.retry}
          />
          <CurrentPlanCard
            plan={plan.data}
            isLoading={plan.isLoading}
            error={plan.error}
            onRetry={plan.retry}
          />
        </div>

        <QuickActions />

        {/* Community — official Telegram channel (opens in a new tab). */}
        <TelegramCommunityCard />

        {/* §28: recent wallet ledger + notifications, latest 5, with links. */}
        <div className="grid gap-6 xl:grid-cols-2">
          <RecentTransactions />
          <RecentNotifications />
        </div>

        {/* Team snapshot (Section 9 §42) — counts + commission. */}
        <TeamSummaryCard
          summary={team.data}
          isLoading={team.isLoading}
          error={team.error}
          onRetry={team.retry}
        />

        <EcosystemGrid />

        {/* About / information */}
        <section aria-labelledby="about-heading">
          <h2 id="about-heading" className="mb-3 text-sm font-semibold text-surface-800">
            About the platform
          </h2>
          <div className="rounded-2xl border border-surface-200 bg-surface-50 p-5">
            <p className="text-sm leading-relaxed text-surface-600">
              Manage your account, view available platform features, track your balance, and
              review your activity from one dashboard. This is a development build — financial
              modules are enabled section by section.
            </p>
          </div>
        </section>
      </div>
    </PageContainer>
  );
}
