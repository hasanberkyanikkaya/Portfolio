import { GlassCard } from './GlassCard'
import type { BreadthComponent, MomentumComponent, VixComponent } from '../types/api'
import { formatPct, formatScore } from '../utils/format'

function Row({
  name,
  detail,
  score,
}: {
  name: string
  detail: string
  score: string | null
}) {
  // Width via inline style — Tailwind v4's scanner can't see dynamic classes.
  const width = score === null ? 0 : Math.min(Math.max(Number(score), 0), 100)
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
      <span className="w-40 font-display text-sm font-semibold tracking-wide">{name}</span>
      <span className="min-w-48 flex-1 text-xs text-ink-muted">
        {score === null ? 'unavailable today' : detail}
      </span>
      <div className="flex items-center gap-3">
        <div className="h-1.5 w-28 overflow-hidden rounded-full bg-white/10">
          <div className="h-full rounded-full bg-accent" style={{ width: `${width}%` }} />
        </div>
        <span className="w-10 text-right font-mono text-sm tabular-nums">
          {score === null ? '—' : formatScore(score)}
        </span>
      </div>
    </div>
  )
}

export function SentimentComponents({
  vix,
  momentum,
  breadth,
}: {
  vix: VixComponent | null
  momentum: MomentumComponent | null
  breadth: BreadthComponent | null
}) {
  return (
    <GlassCard className="px-6 py-5">
      <h2 className="text-xs uppercase tracking-widest text-ink-muted">
        Score Components (0 = fear · 100 = greed)
      </h2>
      <div className="mt-4 space-y-3">
        <Row
          name="VIX vs 1y avg"
          detail={
            vix
              ? `VIX ${vix.latest_close} · 1y avg ${vix.avg_252} (${formatPct(vix.pct_vs_avg)})`
              : ''
          }
          score={vix?.score ?? null}
        />
        <Row
          name="SPY momentum"
          detail={momentum ? `${formatPct(momentum.pct_from_ma125)} vs 125-day MA (${momentum.ma125})` : ''}
          score={momentum?.score ?? null}
        />
        <Row
          name="52-week breadth"
          detail={
            breadth
              ? `${breadth.new_highs} highs / ${breadth.new_lows} lows of ${breadth.universe_size} NASDAQ stocks`
              : ''
          }
          score={breadth?.score ?? null}
        />
      </div>
    </GlassCard>
  )
}
