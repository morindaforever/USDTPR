import { useState } from 'react';
import { Alert, Button, Modal } from '@/components';
import { supportService } from '@/services/supportService';

interface NewConversationModalProps {
  open: boolean;
  onClose: () => void;
  onCreated: (conversationId: string) => void;
}

const SUBJECT_PRESETS = [
  'Deposit not showing',
  'Withdrawal question',
  'VIP plan question',
  'Account issue',
  'Referral question',
  'Other',
];

/**
 * New conversation form (§30–§33). Plain text only; the backend enforces
 * subject/message presence, length caps, link-scheme checks, and the
 * per-hour creation rate limit — its error envelope is authoritative.
 */
export function NewConversationModal({ open, onClose, onCreated }: NewConversationModalProps) {
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      const envelope = await supportService.create({ subject: subject.trim(), message: message.trim() });
      if (!envelope.success || !envelope.data) {
        const detail = envelope.errors
          ? Object.values(envelope.errors).flat().join(' ')
          : envelope.message;
        setError(detail || 'Unable to create the conversation.');
        return;
      }
      setSubject('');
      setMessage('');
      onCreated(envelope.data.conversation_id);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Unable to create the conversation.');
    } finally {
      setSubmitting(false);
    }
  };

  const canSubmit = subject.trim().length > 0 && message.trim().length > 0 && !submitting;

  return (
    <Modal
      open={open}
      onClose={() => {
        if (!submitting) onClose();
      }}
      title="New Conversation"
      description="Describe your question — the support team replies here."
    >
      <div className="space-y-4">
        <div>
          <label htmlFor="support-subject" className="mb-1 block text-xs font-medium text-surface-600">
            Subject
          </label>
          <input
            id="support-subject"
            value={subject}
            maxLength={200}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="e.g. Withdrawal question"
            className="w-full rounded-xl border border-surface-200 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {SUBJECT_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => setSubject(preset)}
                className="rounded-full bg-surface-100 px-2.5 py-1 text-[11px] font-medium text-surface-600 transition-colors hover:bg-brand-50 hover:text-brand-700"
              >
                {preset}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label htmlFor="support-message" className="mb-1 block text-xs font-medium text-surface-600">
            Message
          </label>
          <textarea
            id="support-message"
            value={message}
            maxLength={5000}
            rows={5}
            onChange={(e) => setMessage(e.target.value)}
            placeholder="Include any details that help us assist you."
            className="w-full resize-none rounded-xl border border-surface-200 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
          <p className="mt-1 text-right text-[11px] text-surface-400">
            {message.length}/5000
          </p>
        </div>

        {error && (
          <Alert tone="danger" title="Could not create conversation">
            {error}
          </Alert>
        )}

        <div className="flex gap-2">
          <Button variant="secondary" fullWidth onClick={onClose} disabled={submitting}>
            Cancel
          </Button>
          <Button fullWidth isLoading={submitting} disabled={!canSubmit} onClick={() => void submit()}>
            Create Conversation
          </Button>
        </div>
      </div>
    </Modal>
  );
}
