import { useId, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  /** Visible label rendered above the field. */
  label?: string;
  /** Helper text rendered below the field when there is no error. */
  hint?: string;
  /** Validation message; switches the field to its error state. */
  error?: string;
  /** Icon rendered inside the field's leading edge. */
  leadingIcon?: ReactNode;
}

/** Styled text input — the base of every form. Password fields get an
 * accessible show/hide toggle. */
export function Input({
  label,
  hint,
  error,
  leadingIcon,
  className,
  id,
  type,
  ...props
}: InputProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const messageId = `${inputId}-message`;
  const [showPassword, setShowPassword] = useState(false);
  const isPassword = type === 'password';
  const resolvedType = isPassword && showPassword ? 'text' : type;

  return (
    <div className="flex w-full flex-col gap-1.5">
      {label && (
        <label
          htmlFor={inputId}
          className="text-[13px] font-medium text-surface-600"
        >
          {label}
        </label>
      )}
      <div className="relative">
        {leadingIcon && (
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-surface-500">
            {leadingIcon}
          </span>
        )}
        <input
          id={inputId}
          type={resolvedType}
          aria-invalid={Boolean(error)}
          aria-describedby={error || hint ? messageId : undefined}
          className={cn(
            'h-11 w-full rounded-xl border bg-surface-100 px-3.5 text-sm text-surface-800',
            'placeholder:text-surface-500 transition-colors caret-brand-400',
            'focus:outline-none focus:ring-2 focus:ring-offset-0',
            'disabled:cursor-not-allowed disabled:bg-surface-200 disabled:text-surface-500',
            error
              ? 'border-danger-300 focus:border-danger-500 focus:ring-danger-500/30'
              : 'border-surface-200 hover:border-surface-300 focus:border-brand-500/60 focus:ring-brand-500/25',
            leadingIcon && 'pl-10',
            isPassword && 'pr-11',
            className,
          )}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword((visible) => !visible)}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            aria-pressed={showPassword}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1.5 text-surface-500 transition-colors hover:text-surface-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/40"
          >
            {showPassword ? (
              <EyeOff className="h-4 w-4" aria-hidden />
            ) : (
              <Eye className="h-4 w-4" aria-hidden />
            )}
          </button>
        )}
      </div>
      {(error || hint) && (
        <p
          id={messageId}
          className={cn('text-xs', error ? 'text-danger-600' : 'text-surface-500')}
        >
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
