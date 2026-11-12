import { GlassCard } from './GlassCard'
import type { SectorPerformance } from '../types/api'
import { formatPct, pnlColorClass } from '../utils/format'

const HEADERS = [
  { label: 'Sector', align: 'text-left' },
  { label: 'ETF', align: 'text-left' },
  { label: 'Daily %', align: 'text-right' },
  { label: 'Weekly %', align: 'text-right' },
]

export function SectorTable({ sectors }: { sectors: SectorPerformance[] }) {
  return (
    <GlassCard>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10 text-xs uppercase tracking-widest text-ink-muted">
              {HEADERS.map(({ label, align }) => (
                <th key={label} className={`px-4 py-3 font-medium ${align}`}>
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sectors.map((s) => (
              <tr key={s.symbol} className="border-b border-white/5 hover:bg-white/[0.03]">
                <td className="px-4 py-3">{s.name}</td>
                <td className="px-4 py-3 font-display font-semibold tracking-wide">
                  {s.symbol}
                </td>
                <td
                  className={`px-4 py-3 text-right font-mono tabular-nums ${pnlColorClass(s.daily_change_pct)}`}
                >
                  {formatPct(s.daily_change_pct)}
                </td>
                <td
                  className={`px-4 py-3 text-right font-mono tabular-nums ${pnlColorClass(s.weekly_change_pct)}`}
                >
                  {formatPct(s.weekly_change_pct)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassCard>
  )
}
