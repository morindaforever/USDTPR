import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, LifeBuoy } from 'lucide-react';
import { Card } from '@/components';
import { PageContainer } from '@/components/PageContainer';
import { FAQ_CATEGORIES } from '@/data/faq';
import { cn } from '@/utils/cn';

/**
 * Help center (Section 11 §22–§26): categorized FAQ accordions over the
 * structured data module, plus a link into personal support. Content lives
 * in src/data/faq.ts — not hard-coded in this component.
 */
export function HelpPage() {
  const [openKey, setOpenKey] = useState<string | null>(null);

  return (
    <PageContainer
      title="Help Center"
      subtitle="Answers about deposits, VIP, rewards, referrals, and withdrawals."
    >
      <div className="space-y-6">
        {/* Personal support entry */}
        <Link
          to="/support"
          className="flex items-center gap-3 rounded-2xl border border-brand-200 bg-brand-50/60 p-4 transition-colors hover:bg-brand-50"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white">
            <LifeBuoy className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-surface-900">Need personal help?</p>
            <p className="text-xs text-surface-500">
              Open a support conversation and the team will reply in-app.
            </p>
          </div>
        </Link>

        {/* FAQ categories (§23) */}
        {FAQ_CATEGORIES.map((category) => (
          <section key={category.id} aria-labelledby={`faq-${category.id}`}>
            <h2
              id={`faq-${category.id}`}
              className="mb-2.5 font-display text-base font-bold text-surface-900"
            >
              {category.title}
            </h2>
            <Card>
              <ul className="divide-y divide-surface-100">
                {category.items.map((item, index) => {
                  const key = `${category.id}-${index}`;
                  const open = openKey === key;
                  return (
                    <li key={key}>
                      <button
                        type="button"
                        aria-expanded={open}
                        onClick={() => setOpenKey(open ? null : key)}
                        className="flex w-full items-center justify-between gap-3 px-4 py-3.5 text-left"
                      >
                        <span className="text-sm font-medium text-surface-800">{item.question}</span>
                        <ChevronDown
                          className={cn(
                            'h-4 w-4 shrink-0 text-surface-400 transition-transform',
                            open && 'rotate-180',
                          )}
                          aria-hidden
                        />
                      </button>
                      {open && (
                        <p className="px-4 pb-4 text-sm leading-relaxed text-surface-600">
                          {item.answer}
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            </Card>
          </section>
        ))}
      </div>
    </PageContainer>
  );
}
