import { cn } from '@/utils/cn';

/** Inline SVG brand mark — no network dependency, theme-aware via props. */
export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={cn('h-8 w-8', className)} aria-hidden>
      <defs>
        <linearGradient id="logo-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#23a67d" />
          <stop offset="1" stopColor="#0f4639" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#logo-grad)" />
      <path
        d="M20 22h6.5v13.5c0 4.4 2.6 7 6.9 7s6.9-2.6 6.9-7V22H47v14.1c0 7.8-5.4 12.6-13.6 12.6S20 43.9 20 36.1V22z"
        fill="#fff"
      />
      <circle cx="32" cy="14" r="3.5" fill="#fec84b" />
    </svg>
  );
}
