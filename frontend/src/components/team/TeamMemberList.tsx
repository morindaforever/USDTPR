import { formatDate } from '@/utils/format';
import type { TeamMember } from '@/types';

const STATUS_TONES: Record<TeamMember['status'], string> = {
  ACTIVE: 'bg-brand-500/12 text-brand-400 ring-brand-500/30',
  SUSPENDED: 'bg-accent-500/12 text-accent-600 ring-accent-500/30',
  BANNED: 'bg-danger-500/12 text-danger-600 ring-danger-500/30',
};

/**
 * Team member list (§29): public projections only — user ID, display name,
 * join date, account status, level. No emails, phones, or wallet data.
 */
export function TeamMemberList({ members }: { members: TeamMember[] }) {
  if (members.length === 0) {
    return (
      <p className="rounded-2xl border border-dashed border-surface-200 p-5 text-center text-sm text-surface-500">
        No team members at this level yet.
      </p>
    );
  }
  return (
    <ul className="space-y-2.5">
      {members.map((member) => (
        <li
          key={member.user_id}
          className="flex items-center justify-between gap-3 rounded-2xl border border-surface-200 bg-surface-50 p-4"
        >
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-surface-800">
              {member.full_name || 'Member'}
              <span className="ml-2 font-mono text-[11px] font-normal text-surface-400">
                {member.user_id}
              </span>
            </p>
            <p className="mt-0.5 text-xs text-surface-500">
              Level {member.level} · Joined {formatDate(member.joined_at)}
            </p>
          </div>
          <span
            className={`shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${STATUS_TONES[member.status] ?? STATUS_TONES.ACTIVE}`}
          >
            {member.status}
          </span>
        </li>
      ))}
    </ul>
  );
}
