import { Card } from '@/components/Card';
import { TelegramIcon } from '@/components/TelegramIcon';
import { TELEGRAM_CHANNEL_URL } from '@/constants';

/**
 * Telegram community CTA — reused on the dashboard and the account page.
 * Purely a static external link: no API call, no auth, opens the official
 * channel in a new tab. Anchor styling mirrors the design system's
 * secondary Button so it reads as part of the existing UI.
 */
export function TelegramCommunityCard() {
  return (
    <Card className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3.5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/15 text-sky-400">
          <TelegramIcon className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-surface-800">Join our Telegram</p>
          <p className="mt-0.5 text-xs leading-relaxed text-surface-500">
            Get updates, announcements and community information.
          </p>
        </div>
      </div>
      <a
        href={TELEGRAM_CHANNEL_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-xl bg-surface-200 px-4 text-sm font-semibold text-surface-800 transition-colors duration-150 hover:bg-surface-300 active:bg-surface-300/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-surface-400 focus-visible:ring-offset-2 focus-visible:ring-offset-surface-950"
      >
        <TelegramIcon className="h-4 w-4" aria-hidden />
        Join Telegram
      </a>
    </Card>
  );
}
