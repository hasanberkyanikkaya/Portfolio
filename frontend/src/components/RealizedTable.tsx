import { GlassCard } from './GlassCard'
import { EmptyState } from './EmptyState'
import { ErrorBanner } from './ErrorBanner'
import { useRealized } from '../hooks/useRealized'
import {
  formatMoney,
  formatQuantity,
  formatSignedMoney,
  pnlColorClass,
} from '../utils/format'

const HEADERS = [
  { label: 'Ticker', align: 'text-left' },
  { label: 'Qty', align: 'text-right' },
  { label: 'Buy Price', align: 'text-right' },
  { label: 'Sale Price', align: 'text-right' },
  { label: 'Realized P&L', align: 'text-right' },
  { label: 'Sale Date', align: 'text-right' },
]

export function RealizedTable() {
  const { data, isPending, isError, error } = useRealized()

  return (
    <div className="space-y-3">
      {isError && <ErrorBanner error={error} />}
      <GlassCard>
        {isPending ? (
          <div className="space-y-3 p-6">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded bg-white/5" />
            ))}
          </div>
        ) : !data || data.trades.length === 0 ? (
          <EmptyState message="No closed trades yet." />
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
                {data.trades.map((t) => (
                  <tr
                    key={t.id}
                    className="border-b border-white/5 hover:bg-white/[0.03]"
                  >
                    <td className="px-4 py-3 font-display font-semibold tracking-wide">
                      {t.ticker}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">
                      {formatQuantity(t.quantity)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">
                      {formatMoney(t.purchase_price)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums">
                      {formatMoney(t.sale_price)}
                    </td>
                    <td
                      className={`px-4 py-3 text-right font-mono tabular-nums ${pnlColorClass(t.realized_pnl)}`}
                    >
                      {formatSignedMoney(t.realized_pnl)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono tabular-nums text-ink-muted">
                      {t.sale_date}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-white/10">
                  <td colSpan={4} className="px-4 py-3 text-xs uppercase tracking-widest text-ink-muted">
                    Total Realized P&L
                  </td>
                  <td
                    className={`px-4 py-3 text-right font-mono font-semibold tabular-nums ${pnlColorClass(data.total_realized_pnl)}`}
                  >
                    {formatSignedMoney(data.total_realized_pnl)}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </GlassCard>
    </div>
  )
}
