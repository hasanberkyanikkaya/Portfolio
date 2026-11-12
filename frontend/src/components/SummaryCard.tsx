import { GlassCard } from './GlassCard'
import { usePositions } from '../hooks/usePositions'
import { formatMoney, formatSignedMoney, pnlColorClass } from '../utils/format'

function Stat({
  label,
  value,
  valueClass = '',
  caption,
}: {
  label: string
  value: string
  valueClass?: string
  caption?: string
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-ink-muted">{label}</div>
      <div className={`mt-1 font-mono text-2xl tabular-nums ${valueClass}`}>{value}</div>
      {caption && <div className="mt-1 text-xs text-ink-muted">{caption}</div>}
    </div>
  )
}

export function SummaryCard() {
  const { data, isPending } = usePositions()

  return (
    <GlassCard glow className="px-6 py-5">
      {isPending ? (
        <div className="grid animate-pulse grid-cols-1 gap-6 sm:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <div key={i}>
              <div className="h-3 w-24 rounded bg-white/10" />
              <div className="mt-2 h-7 w-32 rounded bg-white/10" />
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
          <Stat
            label="Total Value"
            value={formatMoney(data?.total_market_value ?? null)}
            caption={
              data && data.positions.length > 0 && data.total_market_value === null
                ? 'live prices unavailable'
                : undefined
            }
          />
          <Stat label="Total Cost" value={formatMoney(data?.total_cost_basis ?? null)} />
          <Stat
            label="Unrealized P&L"
            value={formatSignedMoney(data?.total_unrealized_pnl ?? null)}
            valueClass={pnlColorClass(data?.total_unrealized_pnl ?? null)}
          />
        </div>
      )}
    </GlassCard>
  )
}
