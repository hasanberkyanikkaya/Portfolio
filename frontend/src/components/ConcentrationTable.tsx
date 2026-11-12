import { GlassCard } from './GlassCard'
import { formatMoney, formatWeightPct } from '../utils/format'
import type { PositionWeight, SectorWeight } from '../types/api'

// Flag thresholds mirror the backend rules (services/protect.py).
const POSITION_FLAG_PCT = 20
const SECTOR_FLAG_PCT = 40

function WeightBar({ pct }: { pct: string }) {
  return (
    <div className="h-1.5 w-full rounded-full bg-white/10">
      <div
        className="h-full rounded-full bg-accent/40"
        style={{ width: `${Math.min(Number(pct), 100)}%` }}
      />
    </div>
  )
}

function ConcentrationTag() {
  return (
    <span className="rounded-full border border-white/15 px-2 py-0.5 text-[10px] uppercase tracking-wider text-ink-muted">
      concentration
    </span>
  )
}

export function ConcentrationTable({
  positions,
  sectors,
}: {
  positions: PositionWeight[]
  sectors: SectorWeight[]
}) {
  return (
    <GlassCard className="p-6">
      <h2 className="text-xs uppercase tracking-widest text-ink-muted">Concentration</h2>

      <div className="mt-4 space-y-3">
        {positions.map((p) => (
          <div key={p.ticker} className="grid grid-cols-[6rem_1fr_auto] items-center gap-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="font-display text-sm font-semibold">{p.ticker}</span>
                {Number(p.weight_pct) > POSITION_FLAG_PCT && <ConcentrationTag />}
              </div>
              <div className="text-xs text-ink-muted">{p.sector}</div>
            </div>
            <WeightBar pct={p.weight_pct} />
            <div className="text-right font-mono text-sm tabular-nums">
              <div>{formatWeightPct(p.weight_pct)}</div>
              <div className="text-xs text-ink-muted">
                {formatMoney(p.value)}
                {p.weight_basis === 'cost' && ' (cost)'}
              </div>
            </div>
          </div>
        ))}
      </div>

      {sectors.length > 0 && (
        <>
          <h3 className="mt-6 text-[10px] uppercase tracking-widest text-ink-muted">
            By sector
          </h3>
          <div className="mt-3 space-y-3">
            {sectors.map((s) => (
              <div key={s.sector} className="grid grid-cols-[10rem_1fr_auto] items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm">{s.sector}</span>
                  {s.sector !== 'Unknown' && Number(s.weight_pct) > SECTOR_FLAG_PCT && (
                    <ConcentrationTag />
                  )}
                </div>
                <WeightBar pct={s.weight_pct} />
                <span className="text-right font-mono text-sm tabular-nums">
                  {formatWeightPct(s.weight_pct)}
                </span>
              </div>
            ))}
          </div>
        </>
      )}
    </GlassCard>
  )
}
