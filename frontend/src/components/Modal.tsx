import { useEffect, type ReactNode } from 'react';
import { X } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  /** Renders as a bottom sheet on mobile, centered dialog on desktop. */
  variant?: 'sheet' | 'centered';
}

/**
 * Accessible dialog. Focus is moved into the dialog on open, Escape closes
 * it, and background scrolling is locked while visible.
 */
export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  variant = 'sheet',
}: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <button
        type="button"
        aria-label="Close dialog"
        className="absolute inset-0 bg-surface-950/50 backdrop-blur-[2px] animate-fade-in"
        onClick={onClose}
      />
      <div
        className={cn(
          'relative w-full bg-white shadow-card-hover animate-scale-in',
          variant === 'sheet'
            ? 'rounded-t-2xl p-5 pb-8 sm:max-w-md sm:rounded-2xl sm:pb-5'
            : 'm-4 max-w-md rounded-2xl p-5',
        )}
      >
        {variant === 'sheet' && (
          <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-surface-200 sm:hidden" />
        )}
        <div className="mb-3 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-base font-semibold text-surface-900">{title}</h2>}
            {description && (
              <p className="mt-0.5 text-sm text-surface-500">{description}</p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-surface-400 transition-colors hover:bg-surface-100 hover:text-surface-600"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        {children && <div className="text-sm text-surface-700">{children}</div>}
        {footer && <div className="mt-5 flex gap-2">{footer}</div>}
      </div>
    </div>
  );
}
