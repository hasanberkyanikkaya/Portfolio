import { GlassCard } from './GlassCard'
import { EmptyState } from './EmptyState'
import { ErrorBanner } from './ErrorBanner'
import { usePositions } from '../hooks/usePositions'
import { useTechnical } from '../hooks/useTechnical'
import { useDeletePosition } from '../hooks/useMutations'
import {
  formatMoney,
  formatPct,
  formatQuantity,
  formatSignedMoney,
  pnlColorClass,
} from '../utils/format'
import type { PositionWithPnL, StockTechnical, TechnicalLabel } from '../types/api'

const HEADERS = [
  { label: 'Ticker', align: 'text-left' },
  { label: 'Qty', align: 'text-right' },
  { label: 'Buy Price', align: 'text-right' },
  { label: 'Current', align: 'text-right' },
  { label: 'Trend', align: 'text-left' },
  { label: 'MA200', align: 'text-right' },
  { label: '52W H·L', align: 'text-right' },
  { label: 'Market Value', align: 'text-right' },
  { label: 'P&L $', align: 'text-right' },
  { label: 'P&L %', align: 'text-right' },
  { label: '', align: 'text-right' },
]

// Full literal class strings — Tailwind v4's scanner cannot see concatenation.
const LABEL_PILLS: Record<TechnicalLabel, { text: string; classes: string }> = {
  strong: { text: 'Strong', classes: 'border-profit/30 bg-profit/10 text-profit' },
  weak: { text: 'Weak', classes: 'border-loss/30 bg-loss/10 text-loss' },
  neutral: { text: 'Neutral', classes: 'border-white/10 bg-white/5 text-ink-muted' },
}

function TrendPill({ label }: { label: TechnicalLabel | null }) {
  if (label === null) return <span className="text-ink-muted">—</span>
  const pill = LABEL_PILLS[label]
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${pill.classes}`}
    >
      {pill.text}
    </span>
  )
}

function Ma200Cell({ tech }: { tech: StockTechnical | undefined }) {
  if (!tech || tech.above_ma200 === null) {
    return <span className="text-ink-muted">—</span>
  }
  const ma50Hint =
    tech.above_ma50 === null
      ? ''
      : ` · ${tech.above_ma50 ? 'above' : 'below'} MA50 (${formatPct(tech.pct_from_ma50)})`
  return (
    <span
      className={pnlColorClass(tech.pct_from_ma200)}
      title={`${tech.above_ma200 ? 'Above' : 'Below'} MA200${ma50Hint}`}
    >
      {tech.above_ma200 ? '↑' : '↓'} {formatPct(tech.pct_from_ma200)}
    </span>
  )
}

function HighLowCell({ tech }: { tech: StockTechnical | undefined }) {
  if (!tech || tech.pct_from_high_52w === null) {
    return <span className="text-ink-muted">—</span>
  }
  return (
    <span
      className="text-ink-muted"
      title={`52-week closing high ${formatMoney(tech.high_52w)} · low ${formatMoney(tech.low_52w)}`}
    >
      {formatPct(tech.pct_from_high_52w)} · {formatPct(tech.pct_from_low_52w)}
    </span>
  )
}

interface PositionsTableProps {
  onClose: (position: PositionWithPnL) => void
  onNews: (position: PositionWithPnL) => void
}

export function PositionsTable({ onClose, onNews }: PositionsTableProps) {
  const { data, isPending, isError, error } = usePositions()
  const { data: technical } = useTechnical()
  const deleteMutation = useDeletePosition()

  // Technical data is a best-effort overlay: while loading (or if it failed),
  // the table still renders and the technical cells show "—".
  const tech = new Map<string, StockTechnical>(
    technical?.stocks.map((s) => [s.ticker, s]) ?? [],
  )

  function handleDelete(position: PositionWithPnL) {
    if (
      window.confirm(
        `Delete ${position.ticker} (${formatQuantity(position.quantity)} shares) without recording a trade?`,
      )
    ) {
      deleteMutation.mutate(position.id)
    }
  }

  return (
    <div className="space-y-3">
      {isError && <ErrorBanner error={error} />}
      {deleteMutation.isError && <ErrorBanner error={deleteMutation.error} />}
      <GlassCard>
        {isPending ? (
          <div className="space-y-3 p-6">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded bg-white/5" />
            ))}
          </div>
        ) : !data || data.positions.length === 0 ? (
          <EmptyState message="No open positions — add your first one above." />
        ) : (
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
                {data.positions.map((p) => {
                  const t = tech.get(p.ticker)
                  return (
                    <tr
                      key={p.id}
                      onClick={() => onNews(p)}
                      title={`Show recent ${p.ticker} news`}
                      className="cursor-pointer border-b border-white/5 last:border-b-0 hover:bg-white/[0.03]"
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="font-display font-semibold tracking-wide">
                          {p.ticker}
                        </span>
                        {p.price_status === 'unavailable' && (
                          <span className="ml-2 rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-300">
                            No quote
                          </span>
                        )}
                        {t?.earnings_this_week === true && (
                          <span
                            title={`Earnings this week${t.earnings_date ? ` — ${t.earnings_date}` : ''}`}
                            className="ml-2 rounded-full border border-amber-400/30 bg-amber-400/10 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-amber-300"
                          >
                            ER
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {formatQuantity(p.quantity)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {formatMoney(p.purchase_price)}
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {formatMoney(p.current_price)}
                      </td>
                      <td className="px-4 py-3">
                        <TrendPill label={t?.label ?? null} />
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums whitespace-nowrap">
                        <Ma200Cell tech={t} />
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums whitespace-nowrap">
                        <HighLowCell tech={t} />
                      </td>
                      <td className="px-4 py-3 text-right font-mono tabular-nums">
                        {formatMoney(p.market_value)}
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-mono tabular-nums ${pnlColorClass(p.unrealized_pnl)}`}
                      >
                        {formatSignedMoney(p.unrealized_pnl)}
                      </td>
                      <td
                        className={`px-4 py-3 text-right font-mono tabular-nums ${pnlColorClass(p.unrealized_pnl_pct)}`}
                      >
                        {formatPct(p.unrealized_pnl_pct)}
                      </td>
                      <td className="px-4 py-3 text-right whitespace-nowrap">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onClose(p)
                          }}
                          className="rounded-md border border-white/10 bg-white/[0.06] px-2.5 py-1 text-xs text-ink transition-colors hover:border-accent/40 hover:text-accent"
                        >
                          Close
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            handleDelete(p)
                          }}
                          disabled={deleteMutation.isPending}
                          className="ml-2 rounded-md border border-white/10 bg-white/[0.06] px-2.5 py-1 text-xs text-ink-muted transition-colors hover:border-loss/40 hover:text-loss disabled:opacity-50"
                        >
                          Delete
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  )
}
