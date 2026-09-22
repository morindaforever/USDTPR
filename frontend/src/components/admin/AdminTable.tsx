import type { ReactNode } from 'react';
import { AlertTriangle, ChevronLeft, ChevronRight, RefreshCw, Search } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface AdminTableProps<T> {
  columns: Array<{
    key: string;
    header: string;
    render: (row: T) => ReactNode;
    className?: string;
  }>;
  rows: T[] | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  emptyMessage: string;
  rowKey: (row: T) => string;
  /** Server-driven pagination controls (§78). */
  page: number;
  pageCount: number;
  onPageChange: (page: number) => void;
  count: number;
  /** Server-driven search box. */
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;
  /** Extra filter controls (chips/selects) rendered next to search. */
  filters?: ReactNode;
  /** Mobile: render rows as stacked cards instead of a wide table (§74). */
  renderCard?: (row: T) => ReactNode;
}

/**
 * One table implementation for every admin page (§73): server pagination,
 * server search, loading/empty/error states, responsive card layout.
 */
export function AdminTable<T>({
  columns,
  rows,
  isLoading,
  error,
  onRetry,
  emptyMessage,
  rowKey,
  page,
  pageCount,
  onPageChange,
  count,
  searchValue,
  onSearchChange,
  searchPlaceholder,
  filters,
  renderCard,
}: AdminTableProps<T>) {
  return (
    <div className="space-y-3">
      {(onSearchChange || filters) && (
        <div className="flex flex-wrap items-center gap-2">
          {onSearchChange !== undefined && (
            <div className="relative min-w-0 flex-1 sm:max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-surface-500" aria-hidden />
              <input
                type="search"
                value={searchValue ?? ''}
                onChange={(e) => onSearchChange?.(e.target.value)}
                placeholder={searchPlaceholder ?? 'Search…'}
                className="w-full rounded-xl border border-surface-200 bg-surface-50 py-2.5 pl-9 pr-3 text-sm text-surface-100 placeholder:text-surface-500 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
              />
            </div>
          )}
          {filters}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="h-12 animate-pulse rounded-xl bg-surface-200/40" />
          ))}
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-surface-200 bg-surface-50 p-6 text-center">
          <AlertTriangle className="mx-auto h-6 w-6 text-amber-400" aria-hidden />
          <p className="mt-2 text-sm text-surface-300">{error}</p>
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 inline-flex items-center gap-1.5 rounded-xl border border-surface-200 px-3.5 py-2 text-xs font-semibold text-surface-200 hover:bg-surface-200/40"
          >
            <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Retry
          </button>
        </div>
      ) : (rows ?? []).length === 0 ? (
        <div className="rounded-2xl border border-dashed border-surface-200 p-8 text-center">
          <p className="text-sm text-surface-400">{emptyMessage}</p>
        </div>
      ) : (
        <>
          {/* Desktop table */}
          <div className="hidden overflow-hidden rounded-2xl border border-surface-200 md:block">
            <table className="w-full text-left text-sm">
              <thead className="bg-surface-200/40 text-[11px] uppercase tracking-wide text-surface-400">
                <tr>
                  {columns.map((col) => (
                    <th key={col.key} scope="col" className={cn('px-4 py-3 font-semibold', col.className)}>
                      {col.header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-200">
                {(rows ?? []).map((row) => (
                  <tr key={rowKey(row)} className="text-surface-200 transition-colors hover:bg-surface-200/40">
                    {columns.map((col) => (
                      <td key={col.key} className={cn('px-4 py-3', col.className)}>
                        {col.render(row)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards (§74) */}
          <div className="space-y-2 md:hidden">
            {renderCard
              ? (rows ?? []).map((row) => (
                  <div key={rowKey(row)} className="rounded-2xl border border-surface-200 bg-surface-50 p-3">
                    {renderCard(row)}
                  </div>
                ))
              : (rows ?? []).map((row) => (
                  <div key={rowKey(row)} className="space-y-1.5 rounded-2xl border border-surface-200 bg-surface-50 p-3">
                    {columns.map((col) => (
                      <div key={col.key} className="flex items-center justify-between gap-2 text-sm">
                        <span className="text-[11px] uppercase tracking-wide text-surface-500">{col.header}</span>
                        <span className="min-w-0 truncate text-right text-surface-200">{col.render(row)}</span>
                      </div>
                    ))}
                  </div>
                ))}
          </div>

          {/* Pagination (server-driven, §78) */}
          {pageCount > 1 && (
            <div className="flex items-center justify-between gap-3 pt-1 text-xs text-surface-400">
              <span>
                Page {page} of {pageCount} · {count} total
              </span>
              <div className="flex gap-1.5">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => onPageChange(page - 1)}
                  className="rounded-lg border border-surface-200 p-1.5 disabled:opacity-40"
                  aria-label="Previous page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  type="button"
                  disabled={page >= pageCount}
                  onClick={() => onPageChange(page + 1)}
                  className="rounded-lg border border-surface-200 p-1.5 disabled:opacity-40"
                  aria-label="Next page"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
