import { useCallback, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertTriangle, LifeBuoy, Plus, RefreshCw } from 'lucide-react';
import { Button, PageContainer } from '@/components';
import { Skeleton, useDashboardData } from '@/hooks';
import { supportService, type SupportStatusFilter } from '@/services/supportService';
import { formatDate } from '@/utils/format';
import { NewConversationModal } from '@/components/support';
import { cn } from '@/utils/cn';
import type { SupportConversation } from '@/types';

const FILTERS: Array<{ key: SupportStatusFilter; label: string }> = [
  { key: 'ALL', label: 'All' },
  { key: 'OPEN', label: 'Open' },
  { key: 'IN_PROGRESS', label: 'Waiting' },
  { key: 'RESOLVED', label: 'Resolved' },
  { key: 'CLOSED', label: 'Closed' },
];

const STATUS_LABELS: Record<SupportConversation['status'], string> = {
  OPEN: 'Open',
  IN_PROGRESS: 'Waiting for support',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};

const STATUS_TONES: Record<SupportConversation['status'], string> = {
  OPEN: 'bg-brand-500/10 text-brand-400 ring-emerald-200',
  IN_PROGRESS: 'bg-accent-500/10 text-accent-700 ring-amber-200',
  RESOLVED: 'bg-info-50 text-info-700 ring-sky-200',
  CLOSED: 'bg-surface-100 text-surface-600 ring-surface-300',
};

/** Support center (Section 11 §27–§28): the user's own conversations. */
export function SupportPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = (searchParams.get('status') as SupportStatusFilter) || 'ALL';

  const [isNewOpen, setIsNewOpen] = useState(false);

  const listQuery = useDashboardData<SupportConversation[]>(
    () => supportService.list(statusFilter).then((r) => r.data ?? []),
  );

  const setFilter = (filter: SupportStatusFilter) => {
    if (filter === 'ALL') searchParams.delete('status');
    else searchParams.set('status', filter);
    setSearchParams(searchParams, { replace: true });
  };

  const onCreated = useCallback(
    (conversationId: string) => {
      setIsNewOpen(false);
      navigate(`/support/${conversationId}`);
    },
    [navigate],
  );

  return (
    <PageContainer
      title="Support"
      subtitle="Get help from the platform team."
      actions={
        <Button size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsNewOpen(true)}>
          New Conversation
        </Button>
      }
    >
      <div className="space-y-5">
        {/* Status filters (§41) — server-side filtering */}
        <div className="flex gap-2 overflow-x-auto pb-1" role="tablist" aria-label="Filter conversations">
          {FILTERS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={statusFilter === key}
              onClick={() => setFilter(key)}
              className={cn(
                'shrink-0 rounded-full px-3.5 py-1.5 text-xs font-semibold transition-colors',
                statusFilter === key
                  ? 'bg-brand-600 text-surface-800'
                  : 'bg-surface-100 text-surface-600 hover:bg-surface-300',
              )}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Conversation list (§28) */}
        {listQuery.isLoading ? (
          <div className="space-y-2.5">
            <Skeleton className="h-24 w-full rounded-2xl" />
            <Skeleton className="h-24 w-full rounded-2xl" />
          </div>
        ) : listQuery.error ? (
          <div className="rounded-2xl border border-surface-200 bg-surface-50 p-5 text-center">
            <p className="flex items-center justify-center gap-2 text-sm text-surface-600">
              <AlertTriangle className="h-4 w-4 text-accent-600" aria-hidden />
              Unable to load conversations.
            </p>
            <Button variant="outline" size="sm" className="mt-3" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={listQuery.retry}>
              Retry
            </Button>
          </div>
        ) : (listQuery.data ?? []).length === 0 ? (
          <div className="rounded-2xl border border-dashed border-surface-200 p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand-500/12 text-brand-400">
              <LifeBuoy className="h-6 w-6" aria-hidden />
            </div>
            <p className="mt-3 text-sm font-medium text-surface-700">No conversations yet</p>
            <p className="mt-1 text-xs text-surface-500">
              Start a conversation and the support team will reply here.
            </p>
            <Button className="mt-4" size="sm" leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsNewOpen(true)}>
              New Conversation
            </Button>
          </div>
        ) : (
          <ul className="space-y-2.5">
            {(listQuery.data ?? []).map((conversation) => (
              <li key={conversation.conversation_id}>
                <button
                  type="button"
                  onClick={() => navigate(`/support/${conversation.conversation_id}`)}
                  className="w-full rounded-2xl border border-surface-200 bg-surface-50 p-4 text-left transition-colors hover:border-brand-500/30 hover:bg-brand-500/10/30"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-surface-800">
                        {conversation.subject}
                      </p>
                      <p className="mt-0.5 font-mono text-[11px] text-surface-400">
                        {conversation.conversation_id}
                      </p>
                      {conversation.last_message_preview && (
                        <p className="mt-1.5 truncate text-xs text-surface-500">
                          {conversation.last_message_preview}
                        </p>
                      )}
                    </div>
                    <span
                      className={cn(
                        'shrink-0 rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset',
                        STATUS_TONES[conversation.status],
                      )}
                    >
                      {STATUS_LABELS[conversation.status]}
                    </span>
                  </div>
                  <div className="mt-2.5 flex items-center justify-between text-[11px] text-surface-400">
                    <span>Created {formatDate(conversation.created_at)}</span>
                    <span>Updated {formatDate(conversation.last_message_at ?? conversation.updated_at)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <NewConversationModal
        open={isNewOpen}
        onClose={() => setIsNewOpen(false)}
        onCreated={onCreated}
      />
    </PageContainer>
  );
}
