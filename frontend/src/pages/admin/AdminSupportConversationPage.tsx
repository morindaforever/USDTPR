import { useCallback, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Send } from 'lucide-react';
import { adminService } from '@/services/adminService';
import { useDashboardData } from '@/hooks';
import { AdminPageHeader, AdminStatusBadge } from '@/components/admin';
import { Button } from '@/components';
import { PageContainer } from '@/components/PageContainer';
import { formatDateTime } from '@/utils/format';

const STATUS_TRANSITIONS: Record<string, Array<{ key: string; label: string }>> = {
  OPEN: [
    { key: 'IN_PROGRESS', label: 'Take / mark in progress' },
    { key: 'RESOLVED', label: 'Mark resolved' },
    { key: 'CLOSED', label: 'Close' },
  ],
  IN_PROGRESS: [
    { key: 'WAITING_FOR_USER', label: 'Wait for user' },
    { key: 'RESOLVED', label: 'Mark resolved' },
    { key: 'CLOSED', label: 'Close' },
  ],
  WAITING_FOR_USER: [
    { key: 'IN_PROGRESS', label: 'Resume' },
    { key: 'RESOLVED', label: 'Mark resolved' },
  ],
  RESOLVED: [{ key: 'CLOSED', label: 'Close' }],
  CLOSED: [],
};

/** Admin conversation view (§47–48): staff reply + audited status changes. */
export function AdminSupportConversationPage() {
  const params = useParams<{ conversationId: string }>();
  const conversationId = params.conversationId ?? '';
  const navigate = useNavigate();

  const fetcher = useCallback(async () => {
    const response = await adminService.supportConversation(conversationId);
    if (!response.success) throw new Error(response.message || 'Unable to load conversation.');
    return response;
  }, [conversationId]);
  const query = useDashboardData(fetcher);
  const conversation = query.data?.data ?? null;

  const [reply, setReply] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendReply = async () => {
    if (!reply.trim() || busy) return;
    setBusy(true);
    setError(null);
    try {
      const envelope = await adminService.supportReply(conversationId, reply.trim());
      if (!envelope.success) {
        setError(envelope.message || 'Reply failed.');
        return;
      }
      setReply('');
      query.retry();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Reply failed.');
    } finally {
      setBusy(false);
    }
  };

  const changeStatus = async (status: string) => {
    setBusy(true);
    setError(null);
    try {
      const envelope = await adminService.supportStatus(conversationId, status);
      if (!envelope.success) {
        setError(envelope.message || 'Status change failed.');
        return;
      }
      query.retry();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Status change failed.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <PageContainer>
      <div className="mx-auto max-w-3xl">
        <Link to="/admin/support" className="mb-4 inline-flex items-center gap-1.5 text-xs text-surface-400 hover:text-surface-200">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden /> Back to support
        </Link>

        <AdminPageHeader
          title={conversation?.subject ?? 'Conversation'}
          subtitle={conversation ? `${conversation.conversation_id} · user ${conversation.user_id} · ${conversation.user_email}` : undefined}
          actions={conversation && <AdminStatusBadge status={conversation.status} />}
        />

        {query.isLoading && <div className="space-y-2">{[0, 1, 2].map((i) => <div key={i} className="h-16 animate-pulse rounded-2xl bg-white/5" />)}</div>}
        {query.error && (
          <div className="rounded-2xl border border-white/10 bg-surface-900 p-6 text-center">
            <p className="text-sm text-surface-300">{query.error}</p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={query.retry}>Retry</Button>
            <Button variant="ghost" size="sm" className="mt-3 ml-2" onClick={() => navigate('/admin/support')}>Back</Button>
          </div>
        )}

        {conversation && (
          <div className="space-y-4">
            {/* Message thread (oldest → newest, §36/§34) */}
            <div className="space-y-2">
              {conversation.messages.length === 0 && (
                <p className="rounded-2xl border border-dashed border-white/10 p-6 text-center text-sm text-surface-400">No messages yet</p>
              )}
              {conversation.messages.map((message) => {
                const isStaff = message.sender_type === 'support';
                return (
                  <div key={message.id} className={`flex ${isStaff ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${isStaff ? 'bg-brand-600/20 text-surface-100' : 'bg-surface-900 text-surface-200'}`}>
                      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-surface-500">
                        {isStaff ? 'Support' : `User ${message.sender_id}`} · {formatDateTime(message.created_at)}
                      </p>
                      <p className="whitespace-pre-wrap break-words">{message.message}</p>
                    </div>
                  </div>
                );
              })}
            </div>

            {error && <p className="rounded-xl bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</p>}

            {/* Reply composer (hidden on closed, §48) */}
            {conversation.status !== 'CLOSED' ? (
              <div className="rounded-2xl border border-white/10 bg-surface-900 p-3">
                <label htmlFor="admin-reply" className="mb-2 block text-xs font-medium text-surface-400">Reply as support</label>
                <textarea
                  id="admin-reply"
                  value={reply}
                  rows={3}
                  maxLength={2000}
                  onChange={(e) => setReply(e.target.value)}
                  className="w-full resize-none rounded-xl border border-white/10 bg-surface-950 px-3 py-2.5 text-sm text-surface-100 focus:border-brand-500 focus:outline-none"
                />
                <div className="mt-2 flex items-center justify-between">
                  <p className="text-[11px] text-surface-500">Replying notifies the user.</p>
                  <Button size="sm" isLoading={busy} disabled={reply.trim().length === 0} onClick={() => void sendReply()}>
                    <Send className="h-3.5 w-3.5" aria-hidden /> Send reply
                  </Button>
                </div>
              </div>
            ) : (
              <p className="rounded-2xl border border-white/10 bg-surface-900 p-3 text-center text-xs text-surface-400">This conversation is closed.</p>
            )}

            {/* Status transitions (§48) */}
            {STATUS_TRANSITIONS[conversation.status]?.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {STATUS_TRANSITIONS[conversation.status].map((transition) => (
                  <Button key={transition.key} size="sm" variant={transition.key === 'CLOSED' ? 'danger' : 'secondary'} disabled={busy} onClick={() => void changeStatus(transition.key)}>
                    {transition.label}
                  </Button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </PageContainer>
  );
}
