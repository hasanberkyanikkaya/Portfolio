import { ErrorBanner } from './ErrorBanner'
import { EmptyState } from './EmptyState'
import { useTickerNews } from '../hooks/useTickerNews'
import { formatNewsDate } from '../utils/format'

interface NewsDialogProps {
  ticker: string
  onClose: () => void
}

export function NewsDialog({ ticker, onClose }: NewsDialogProps) {
  const { data, isPending, isError, error } = useTickerNews(ticker)

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-void/70 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-lg overflow-hidden rounded-2xl border border-white/10 bg-deep-navy/90 p-6 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xl"
        role="dialog"
        aria-modal="true"
        aria-label={`Recent news for ${ticker}`}
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/60 to-transparent" />
        <div className="flex items-start justify-between">
          <div>
            <h2 className="font-display text-lg font-semibold">
              <span className="text-accent">{ticker}</span> news
            </h2>
            {data && (
              <p className="mt-1 text-xs text-ink-muted">
                Last 7 days · {data.items.length} stories
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-md border border-white/10 bg-white/[0.06] px-2.5 py-1 text-xs text-ink-muted transition-colors hover:text-ink"
          >
            Esc
          </button>
        </div>

        <div className="mt-4">
          {isPending ? (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-12 animate-pulse rounded bg-white/5" />
              ))}
            </div>
          ) : isError ? (
            <ErrorBanner error={error} />
          ) : data.items.length === 0 ? (
            <EmptyState message="No news in the last 7 days." />
          ) : (
            <ul className="max-h-[60vh] space-y-1 overflow-y-auto pr-1">
              {data.items.map((item, i) => (
                <li key={i} className="rounded-lg p-3 transition-colors hover:bg-white/[0.04]">
                  {item.url ? (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-ink transition-colors hover:text-accent"
                    >
                      {item.headline}
                    </a>
                  ) : (
                    <span className="text-sm font-medium text-ink">{item.headline}</span>
                  )}
                  <p className="mt-1 text-xs text-ink-muted">
                    {item.source ? `${item.source} · ` : ''}
                    {formatNewsDate(item.published_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
