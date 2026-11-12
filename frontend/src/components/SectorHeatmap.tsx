import { GlassCard } from './GlassCard'
import type { SectorPerformance } from '../types/api'
import { formatPct, heatmapBgClass } from '../utils/format'

export function SectorHeatmap({ sectors }: { sectors: SectorPerformance[] }) {
  return (
    <GlassCard className="p-4">
      <h2 className="px-1 pb-3 text-xs uppercase tracking-widest text-ink-muted">
        Sector Heatmap — Today
      </h2>
      <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
        {sectors.map((s) => (
          <div
            key={s.symbol}
            className={`rounded-xl p-3 ${heatmapBgClass(s.daily_change_pct)}`}
          >
            <div className="font-display text-sm font-semibold tracking-wide">
              {s.symbol}
            </div>
            <div className="mt-1 font-mono text-xs tabular-nums">
              {formatPct(s.daily_change_pct)}
            </div>
            <div className="mt-0.5 truncate text-[10px] text-ink-muted">{s.name}</div>
          </div>
        ))}
      </div>
    </GlassCard>
  )
}
