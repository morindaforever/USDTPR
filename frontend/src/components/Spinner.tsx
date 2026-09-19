import { Loader2 } from 'lucide-react';
import { cn } from '@/utils/cn';

type SpinnerSize = 'sm' | 'md' | 'lg';

const SIZE_CLASSES: Record<SpinnerSize, string> = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-9 w-9',
};

export function Spinner({
  size = 'md',
  className,
  label = 'Loading',
}: {
  size?: SpinnerSize;
  className?: string;
  label?: string;
}) {
  return (
    <span role="status" aria-live="polite" className={cn('inline-flex', className)}>
      <Loader2 className={cn('animate-spin text-brand-600', SIZE_CLASSES[size])} />
      <span className="sr-only">{label}</span>
    </span>
  );
}
