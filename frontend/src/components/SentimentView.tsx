import { GlassCard } from './GlassCard'
import { EmptyState } from './EmptyState'
import { ErrorBanner } from './ErrorBanner'
import { SentimentGauge } from './SentimentGauge'
import { SentimentComponents } from './SentimentComponents'
import { GlossarySection } from './GlossarySection'
import { useSentiment } from '../hooks/useSentiment'

export function SentimentView() {
  const { data, isPending, isError, error } = useSentiment()

  if (isPending) {
    return (
      <div className="space-y-6">
        {[0, 1].map((i) => (
          <GlassCard key={i}>
            <div className="space-y-3 p-6">
              {[0, 1, 2].map((j) => (
                <div key={j} className="h-9 animate-pulse rounded bg-white/5" />
              ))}
            </div>
          </GlassCard>
        ))}
      </div>
    )
  }

  if (isError && error.status === 404) {
    return (
      <div className="space-y-6">
        <GlassCard>
          <EmptyState message="No Sentiment report yet — it is generated after each market close (16:55 ET)." />
        </GlassCard>
        <GlossarySection />
      </div>
    )
  }

  if (isError || !data) {
    return <ErrorBanner error={error} />
  }

  const { content } = data
  return (
    <div className="space-y-6">
      <SentimentGauge
        score={content.data.score}
        label={content.data.label}
        componentsUsed={content.data.components_used}
      />
      <SentimentComponents
        vix={content.data.vix}
        momentum={content.data.momentum}
        breadth={content.data.breadth}
      />
      <GlassCard className="p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xs uppercase tracking-widest text-ink-muted">
            Sentiment Commentary
          </h2>
          <span className="font-mono text-xs tabular-nums text-ink-muted">
            {data.report_date}
          </span>
        </div>
        <p className="mt-3 whitespace-pre-line text-sm leading-relaxed">{content.text}</p>
        {content.warnings.length > 0 && (
          <p className="mt-3 text-xs text-ink-muted">
            Some data was unavailable: {content.warnings.join(', ')}
          </p>
        )}
      </GlassCard>
      <GlossarySection />
    </div>
  )
}
