import { useCallback, useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AlertTriangle, RefreshCw, RotateCcw, Send } from 'lucide-react';
import { Button, PageContainer } from '@/components';
import { Skeleton } from '@/hooks';
import { supportService } from '@/services/supportService';
import { formatDate } from '@/utils/format';
import { cn } from '@/utils/cn';
import type { SupportConversationDetail, SupportMessage } from '@/types';

const STATUS_LABELS: Record<SupportConversationDetail['status'], string> = {
  OPEN: 'Open',
  IN_PROGRESS: 'Waiting for support',
  RESOLVED: 'Resolved',
  CLOSED: 'Closed',
};

const STATUS_TONES: Record<SupportConversationDetail['status'], string> = {
  OPEN: 'bg-emerald-50 text-emerald-700 ring-emerald-200',
  IN_PROGRESS: 'bg-amber-50 text-amber-700 ring-amber-200',
  RESOLVED: 'bg-sky-50 text-sky-700 ring-sky-200',
  CLOSED: 'bg-surface-100 text-surface-600 ring-surface-200',
};

/**
 * Conversation thread (§34–§39). Messages render as plain text (React
 * escapes by default — XSS payloads display inertly, §75); the thread
 * refreshes manually and on send, no aggressive polling (§45).
 */
export function SupportConversationPage() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const navigate = useNavigate();

  const [conversation, setConversation] = useState<SupportConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const load = useCallback(async () => {
    if (!conversationId) return;
    setLoading(true);
    setLoadError(null);
    try {
      const data = await supportService.detail(conversationId);
      setConversation(data);
    } catch (err: unknown) {
      setLoadError(err instanceof Error ? err.message : 'Unable to load the conversation.');
    } finally {
      setLoading(false);
    }
  }, [conversationId]);

  useEffect(() => {
    void load();
  }, [load]);

  const sendReply = async () => {
    if (!conversationId || sending || reply.trim().length === 0) return;
    setSending(true);
    setSendError(null);
    try {
      const envelope = await supportService.sendMessage(conversationId, reply.trim());
      if (!envelope.success || !envelope.data) {
        const detail = envelope.errors
          ? Object.values(envelope.errors).flat().join(' ')
          : envelope.message;
        setSendError(detail || 'Unable to send the message.');
        return;
      }
      setConversation(envelope.data);
      setReply('');
    } catch (err: unknown) {
      setSendError(err instanceof Error ? err.message : 'Unable to send the message.');
    } finally {
      setSending(false);
    }
  };

  const closeConversation = async () => {
    if (!conversationId || actionBusy) return;
    setActionBusy(true);
    try {
      const envelope = await supportService.close(conversationId);
      if (envelope.success && envelope.data) setConversation(envelope.data);
    } finally {
      setActionBusy(false);
    }
  };

  const reopenConversation = async () => {
    if (!conversationId || actionBusy) return;
    setActionBusy(true);
    try {
      const envelope = await supportService.reopen(conversationId);
      if (envelope.success && envelope.data) setConversation(envelope.data);
      else setSendError(envelope.message);
    } finally {
      setActionBusy(false);
    }
  };

  if (loading) {
    return (
      <PageContainer title="Conversation">
        <div className="space-y-3">
          <Skeleton className="h-16 w-full rounded-2xl" />
          <Skeleton className="h-24 w-full rounded-2xl" />
          <Skeleton className="h-24 w-3/4 rounded-2xl" />
        </div>
      </PageContainer>
    );
  }

  if (loadError || !conversation) {
    return (
      <PageContainer title="Conversation">
        <div className="rounded-2xl border border-surface-200 bg-white p-6 text-center">
          <AlertTriangle className="mx-auto h-8 w-8 text-amber-500" aria-hidden />
          <p className="mt-3 text-sm text-surface-600">{loadError || 'Conversation not found.'}</p>
          <div className="mt-4 flex justify-center gap-2">
            <Button variant="outline" size="sm" onClick={() => navigate('/support')}>Back to Support</Button>
            <Button size="sm" leftIcon={<RefreshCw className="h-4 w-4" />} onClick={() => void load()}>Retry</Button>
          </div>
        </div>
      </PageContainer>
    );
  }

  const closed = conversation.status === 'CLOSED';

  return (
    <PageContainer title="Conversation" subtitle={conversation.subject}>
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-surface-200 bg-white p-4">
          <div className="min-w-0">
            <p className="font-mono text-[11px] text-surface-400">{conversation.conversation_id}</p>
            <p className="mt-0.5 text-xs text-surface-500">
              Created {formatDate(conversation.created_at)} · Updated{' '}
              {formatDate(conversation.last_message_at ?? conversation.updated_at)}
            </p>
          </div>
          <span
            className={cn(
              'rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset',
              STATUS_TONES[conversation.status],
            )}
          >
            {STATUS_LABELS[conversation.status]}
          </span>
        </div>

        {/* Message thread — oldest → newest (§36) */}
        <ul className="space-y-3" aria-label="Message thread">
          {conversation.messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
        </ul>

        {sendError && (
          <p className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700" role="alert">
            {sendError}
          </p>
        )}

        {/* Composer + actions (§37–§38) */}
        {closed ? (
          <div className="rounded-2xl border border-surface-200 bg-surface-50 p-4 text-center">
            <p className="text-sm text-surface-600">
              This conversation is closed. Reopen it if you still need help.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              isLoading={actionBusy}
              leftIcon={<RotateCcw className="h-4 w-4" />}
              onClick={() => void reopenConversation()}
            >
              Reopen Conversation
            </Button>
          </div>
        ) : (
          <div className="rounded-2xl border border-surface-200 bg-white p-4">
            <label htmlFor="reply-message" className="mb-2 block text-xs font-medium text-surface-600">
              Reply
            </label>
            <textarea
              id="reply-message"
              value={reply}
              rows={3}
              maxLength={5000}
              onChange={(e) => setReply(e.target.value)}
              placeholder="Type your message…"
              className="w-full resize-none rounded-xl border border-surface-200 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
            <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2">
              <Button
                variant="ghost"
                size="sm"
                isLoading={actionBusy}
                onClick={() => void closeConversation()}
              >
                Close Conversation
              </Button>
              <Button
                size="sm"
                isLoading={sending}
                disabled={reply.trim().length === 0}
                leftIcon={<Send className="h-4 w-4" />}
                onClick={() => void sendReply()}
              >
                Send Message
              </Button>
            </div>
          </div>
        )}

        <button
          type="button"
          onClick={() => navigate('/support')}
          className="w-full text-center text-xs font-semibold text-surface-500 hover:text-brand-600"
        >
          ← Back to all conversations
        </button>
      </div>
    </PageContainer>
  );
}

function MessageBubble({ message }: { message: SupportMessage }) {
  const isSupport = message.sender_type === 'support';
  return (
    <li className={cn('flex', isSupport ? 'justify-start' : 'justify-end')}>
      <div
        className={cn(
          'max-w-[85%] rounded-2xl px-4 py-3 sm:max-w-[70%]',
          isSupport
            ? 'rounded-tl-sm bg-surface-100 text-surface-900'
            : 'rounded-tr-sm bg-brand-600 text-white',
        )}
      >
        <p className="text-[11px] font-semibold uppercase tracking-wide opacity-70">
          {isSupport ? 'Support' : 'You'} · {formatDate(message.created_at)}
        </p>
        {/* Plain-text rendering: React escapes content — no raw HTML (§33). */}
        <p className="mt-1 whitespace-pre-wrap break-words text-sm">{message.message}</p>
      </div>
    </li>
  );
}
