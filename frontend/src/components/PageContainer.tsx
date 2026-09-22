import type { ReactNode } from 'react';
import { cn } from '@/utils/cn';

export interface PageContainerProps {
  /** Large page title shown at the top of the content area. */
  title?: string;
  /** Optional subtitle under the title. */
  subtitle?: string;
  /** Right-aligned actions next to the title (desktop). */
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** Standard horizontal rhythm for every page rendered inside a layout. */
export function PageContainer({ title, subtitle, actions, children, className }: PageContainerProps) {
  return (
    <div className={cn('mx-auto w-full max-w-6xl px-4 pb-28 pt-5 md:px-8 md:pb-14 md:pt-8', className)}>
      {(title || actions) && (
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            {title && (
              <h1 className="font-display text-xl font-bold tracking-tight text-surface-800 md:text-2xl">
                {title}
              </h1>
            )}
            {subtitle && <p className="mt-1 text-sm text-surface-500">{subtitle}</p>}
          </div>
          {actions && <div className="hidden shrink-0 md:block">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
