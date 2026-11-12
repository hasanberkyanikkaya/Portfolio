import { GlassCard } from './GlassCard'
import type { MaPositioning, RspSpyComparison, RspSpySignal } from '../types/api'
import { formatPct, pnlColorClass } from '../utils/format'

const SIGNAL_LABELS: Record<RspSpySignal, string> = {
  broad_participation: 'Geniş katılım',
  megacap_concentration: 'Mega-cap ağırlıklı',
  neutral: 'Nötr',
}

function Stat({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-ink-muted">{label}</div>
      <div
        className={`mt-1 font-mono text-2xl tabular-nums ${pnlColorClass(value)}`}
      >
        {formatPct(value)}
      </div>
    </div>
  )
}

function MaRow({ ma }: { ma: MaPositioning }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
      <span className="w-24 font-display text-sm font-semibold tracking-wide">
        {ma.symbol}
        <span className="ml-2 text-xs font-normal text-ink-muted">{ma.index}</span>
      </span>
      <span className="text-xs text-ink-muted">
        {ma.above_ma50 ? 'above' : 'below'} 50d MA{' '}
        <span className={`font-mono tabular-nums ${pnlColorClass(ma.pct_from_ma50)}`}>
          {formatPct(ma.pct_from_ma50)}
        </span>
      </span>
      <span className="text-xs text-ink-muted">
        {ma.above_ma200 ? 'above' : 'below'} 200d MA{' '}
        <span className={`font-mono tabular-nums ${pnlColorClass(ma.pct_from_ma200)}`}>
          {formatPct(ma.pct_from_ma200)}
        </span>
      </span>
    </div>
  )
}

export function RspSpyCard({
  rspSpy,
  maPositioning,
}: {
  rspSpy: RspSpyComparison | null
  maPositioning: MaPositioning[]
}) {
  return (
    <GlassCard className="px-6 py-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs uppercase tracking-widest text-ink-muted">
          Market Breadth — RSP vs SPY
        </h2>
        {rspSpy && (
          // Decorative accent stays cyan — the signal badge is a label, not a P&L value.
          <span className="rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-accent">
            {SIGNAL_LABELS[rspSpy.signal]}
          </span>
        )}
      </div>

      {rspSpy ? (
        <div className="mt-4 grid grid-cols-2 gap-6 sm:grid-cols-4">
          <Stat label="RSP Today" value={rspSpy.rsp_daily_pct} />
          <Stat label="SPY Today" value={rspSpy.spy_daily_pct} />
          <Stat label="RSP Week" value={rspSpy.rsp_weekly_pct} />
          <Stat label="SPY Week" value={rspSpy.spy_weekly_pct} />
        </div>
      ) : (
        <p className="mt-4 text-sm text-ink-muted">RSP/SPY data is unavailable today.</p>
      )}

      {maPositioning.length > 0 && (
        <div className="mt-5 space-y-2 border-t border-white/10 pt-4">
          {maPositioning.map((ma) => (
            <MaRow key={ma.symbol} ma={ma} />
          ))}
        </div>
      )}
    </GlassCard>
  )
}
