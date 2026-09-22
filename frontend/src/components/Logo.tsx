import { cn } from '@/utils/cn';

/** Inline SVG brand mark — no network dependency, tuned for dark surfaces. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn('h-8 w-8', className)} aria-hidden>
      <defs>
        <linearGradient id="logo-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#16c07a" />
          <stop offset="1" stopColor="#0a5f3b" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#logo-grad)" />
      <rect width="64" height="64" rx="16" fill="none" stroke="rgb(255 255 255 / 0.18)" strokeWidth="1.5" />
      <path
        d="M21 44V20h5.4l11.6 15.2V20H43v24h-5.2L26 28.6V44h-5z"
        fill="#fff"
      />
      <circle cx="47" cy="17" r="3.5" fill="#f0c75e" />
    </svg>
  );
}
