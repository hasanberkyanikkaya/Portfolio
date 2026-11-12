import { GlassCard } from './GlassCard'
import { EmptyState } from './EmptyState'
import { ErrorBanner } from './ErrorBanner'
import { SectorHeatmap } from './SectorHeatmap'
import { RspSpyCard } from './RspSpyCard'
import { SectorTable } from './SectorTable'
import { useMarketPulse } from '../hooks/useMarketPulse'

export function MarketPulseView() {
  const { data, isPending, isError, error } = useMarketPulse()

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
      <GlassCard>
        <EmptyState message="No Market Pulse yet — it is generated after each market close (16:50 ET)." />
      </GlassCard>
    )
  }

  if (isError || !data) {
    return <ErrorBanner error={error} />
  }

  const { content } = data
  return (
    <div className="space-y-6">
      <SectorHeatmap sectors={content.data.sectors} />
      <RspSpyCard rspSpy={content.data.rsp_spy} maPositioning={content.data.ma_positioning} />
      <SectorTable sectors={content.data.sectors} />
      <GlassCard className="p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xs uppercase tracking-widest text-ink-muted">
            Market Pulse Commentary
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
    </div>
  )
}
