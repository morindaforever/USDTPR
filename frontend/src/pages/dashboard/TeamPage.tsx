import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw, Users } from 'lucide-react';
import { PageContainer } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { referralService } from '@/services/referralService';
import { buildReferralLink } from '@/utils/referral';
import {
  CommissionHistory,
  ReferralLinkCard,
  TeamMemberList,
  TeamStats,
} from '@/components/team';
import type { PaginatedEnvelope, ReferralSummary, TeamMember } from '@/types';

type LevelFilter = 'all' | 1 | 2 | 3;

const MAX_SHOWN_LEVEL = 3;

/**
 * Team/referrals page (Section 9): shareable link, team statistics,
 * commission summary, level-filtered member list, and commission history.
 * All values come from the referral APIs — nothing is computed here.
 */
export function TeamPage() {
  const [level, setLevel] = useState<LevelFilter>('all');
  const [page, setPage] = useState(1);

  const summaryQuery = useDashboardData<ReferralSummary>(() => referralService.summary());
  const [teamData, setTeamData] = useState<PaginatedEnvelope<TeamMember> | null>(null);
  const [teamLoading, setTeamLoading] = useState(true);
  const [teamError, setTeamError] = useState<string | null>(null);
  const [commissions, setCommissions] = useState<PaginatedEnvelope<
    import('@/types').ReferralCommission
  > | null>(null);
  const [commissionsLoading, setCommissionsLoading] = useState(true);
  const [commissionsError, setCommissionsError] = useState<string | null>(null);

  const loadTeam = useCallback(async () => {
    setTeamLoading(true);
    setTeamError(null);
    try {
      const data = await referralService.team({
        ...(level !== 'all' ? { level } : {}),
        page,
      });
      setTeamData(data);
    } catch (err: unknown) {
      setTeamError(err instanceof Error ? err.message : 'Unable to load your team.');
    } finally {
      setTeamLoading(false);
    }
  }, [level, page]);

  const loadCommissions = useCallback(async () => {
    setCommissionsLoading(true);
    setCommissionsError(null);
    try {
      const data = await referralService.commissions({ page: 1 });
      setCommissions(data);
    } catch (err: unknown) {
      setCommissionsError(err instanceof Error ? err.message : 'Unable to load commissions.');
    } finally {
      setCommissionsLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadTeam();
  }, [loadTeam]);

  useEffect(() => {
    void loadCommissions();
  }, [loadCommissions]);

  const summary = summaryQuery.data;
  // Built from the runtime browser origin so the link always matches the
  // deployed domain (never localhost) — the code itself comes from the API.
  const referralLink = summary ? buildReferralLink(summary.referral_code) : '';
  const members = teamData?.data ?? [];
  const pagination = teamData?.pagination;
  const commissionItems = commissions?.data ?? [];

  return (
    <PageContainer
      title="My Team"
      subtitle="Manage your referral network and view commission activity."
    >
      <div className="space-y-6">
        {/* Notice */}
        <div className="rounded-xl bg-info-50 p-3.5 text-sm text-info-900 ring-1 ring-inset ring-sky-200">
          <p>
            <span className="font-semibold">Referral Program.</span> Commission figures are
            calculated from eligible VIP rewards.
          </p>
        </div>

        {summaryQuery.isLoading ? (
          <div className="space-y-3">
            <Skeleton className="h-32 w-full rounded-2xl" />
          </div>
        ) : summaryQuery.error ? (
          <div className="rounded-2xl border border-surface-200 bg-surface-50 p-5 text-center">
            <p className="flex items-center justify-center gap-2 text-sm text-surface-600">
              <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden />
              Unable to load referral information.
            </p>
            <button
              type="button"
              onClick={summaryQuery.retry}
              className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-surface-200 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
            >
              <RefreshCw className="h-4 w-4" aria-hidden /> Retry
            </button>
          </div>
        ) : summary ? (
          <>
            <ReferralLinkCard link={referralLink} code={summary.referral_code} />
            <TeamStats summary={summary} />
          </>
        ) : null}

        {/* Team members with level filters (§51) */}
        <section aria-labelledby="team-members-heading">
          <h2 id="team-members-heading" className="eyebrow mb-3">
            Team Members
          </h2>
          <div className="mb-3 flex flex-wrap gap-2" role="tablist" aria-label="Filter by level">
            {(['all', 1, 2, 3] as LevelFilter[]).slice(0, MAX_SHOWN_LEVEL + 1).map((value) => (
              <button
                key={String(value)}
                type="button"
                role="tab"
                aria-selected={level === value}
                onClick={() => {
                  setLevel(value);
                  setPage(1);
                }}
                className={`rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors ${
                  level === value
                    ? 'bg-brand-600 text-surface-800 shadow-sm'
                    : 'bg-surface-50 text-surface-600 ring-1 ring-inset ring-surface-300 hover:bg-surface-300'
                }`}
              >
                {value === 'all' ? 'All' : `Level ${value}`}
              </button>
            ))}
          </div>
          {teamLoading ? (
            <div className="space-y-2.5">
              <Skeleton className="h-16 w-full rounded-2xl" />
              <Skeleton className="h-16 w-full rounded-2xl" />
            </div>
          ) : teamError ? (
            <div className="rounded-2xl border border-surface-200 bg-surface-50 p-5 text-center">
              <p className="flex items-center justify-center gap-2 text-sm text-surface-600">
                <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden />
                {teamError}
              </p>
              <button
                type="button"
                onClick={loadTeam}
                className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-surface-200 px-4 py-2 text-sm font-semibold text-surface-700 transition-colors hover:bg-surface-50"
              >
                <RefreshCw className="h-4 w-4" aria-hidden /> Retry
              </button>
            </div>
          ) : members.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-surface-200 p-6 text-center">
              <span className="mx-auto flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <Users className="h-5 w-5" aria-hidden />
              </span>
              <p className="mt-2 text-sm font-semibold text-surface-800">No team members yet</p>
              <p className="mt-1 text-xs text-surface-500">
                Share your referral link to invite your first team member.
              </p>
            </div>
          ) : (
            <>
              <TeamMemberList members={members} />
              {pagination && pagination.pages > 1 && (
                <div className="mt-3 flex items-center justify-center gap-3 text-sm">
                  <button
                    type="button"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    className="rounded-xl border border-surface-200 px-3 py-1.5 font-semibold text-surface-700 disabled:opacity-40"
                  >
                    Prev
                  </button>
                  <span className="text-xs text-surface-500">
                    Page {pagination.page} of {pagination.pages}
                  </span>
                  <button
                    type="button"
                    disabled={page >= pagination.pages}
                    onClick={() => setPage((p) => p + 1)}
                    className="rounded-xl border border-surface-200 px-3 py-1.5 font-semibold text-surface-700 disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </section>

        {/* Commission history (§28) */}
        <section aria-labelledby="commission-history-heading">
          <h2 id="commission-history-heading" className="eyebrow mb-3">
            Commission History
          </h2>
          {commissionsLoading ? (
            <div className="space-y-2.5">
              <Skeleton className="h-16 w-full rounded-2xl" />
              <Skeleton className="h-16 w-full rounded-2xl" />
            </div>
          ) : commissionsError ? (
            <p className="rounded-2xl border border-surface-200 bg-surface-50 p-5 text-center text-sm text-surface-600">
              {commissionsError}
            </p>
          ) : (
            <CommissionHistory commissions={commissionItems} />
          )}
        </section>
      </div>
    </PageContainer>
  );
}
