import { PageContainer } from '@/components/PageContainer';

/**
 * Minimal /admin placeholder. The full admin panel (with its own
 * authentication and financial controls) is built in a later section.
 */
export default function AdminPlaceholderPage() {
  return (
    <div className="flex min-h-dvh items-center justify-center bg-surface-950 px-4">
      <PageContainer title="Admin" subtitle="Administrative console placeholder.">
        <div className="rounded-2xl border border-white/10 bg-white/5 p-6 text-center backdrop-blur">
          <p className="text-sm font-semibold text-white">Admin console not yet available</p>
          <p className="mx-auto mt-2 max-w-sm text-xs leading-relaxed text-surface-400">
            Administrative authentication and financial controls arrive in a
            dedicated later section. This route is reserved.
          </p>
          <a
            href="/"
            className="mt-5 inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-500"
          >
            Back to site
          </a>
        </div>
      </PageContainer>
    </div>
  );
}
