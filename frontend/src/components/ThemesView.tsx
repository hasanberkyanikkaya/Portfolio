import { useState } from 'react'
import { GlassCard } from './GlassCard'
import { ErrorBanner } from './ErrorBanner'
import { DisclaimerNote } from './DisclaimerNote'
import { useThemeDetail, useThemes } from '../hooks/useThemes'
import { formatMoney, formatPct, pnlColorClass } from '../utils/format'
import type { ThemeDetailResponse } from '../types/api'

function ThemeStocksTable({ detail }: { detail: ThemeDetailResponse }) {
  return (
    <GlassCard className="overflow-x-auto">
      <div className="px-4 pt-4">
        <p className="text-xs leading-relaxed text-ink-muted">{detail.description}</p>
      </div>
      <table className="mt-2 w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left text-[10px] uppercase tracking-widest text-ink-muted">
            <th className="px-4 py-3 font-medium">Ticker</th>
            <th className="px-4 py-3 font-medium">Industry</th>
            <th className="px-4 py-3 text-right font-medium">Price</th>
            <th className="px-4 py-3 text-right font-medium">Today</th>
          </tr>
        </thead>
        <tbody>
          {detail.stocks.map((stock) => (
            <tr key={stock.ticker} className="border-b border-white/5 last:border-0">
              <td className="px-4 py-3 font-display font-semibold">{stock.ticker}</td>
              <td className="px-4 py-3 text-xs text-ink-muted">{stock.industry ?? '—'}</td>
              <td className="px-4 py-3 text-right font-mono tabular-nums">
                {formatMoney(stock.price)}
              </td>
              <td
                className={`px-4 py-3 text-right font-mono tabular-nums ${pnlColorClass(stock.percent_change)}`}
              >
                {formatPct(stock.percent_change)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {detail.warnings.length > 0 && (
        <p className="px-4 pb-4 pt-2 text-xs text-ink-muted">
          Some data was unavailable: {detail.warnings.join(', ')}
        </p>
      )}
    </GlassCard>
  )
}

export function ThemesView() {
  const [slug, setSlug] = useState<string | null>(null)
  const themes = useThemes()
  const detail = useThemeDetail(slug)

  if (themes.isPending) {
    return (
      <GlassCard>
        <div className="space-y-3 p-6">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-9 animate-pulse rounded bg-white/5" />
          ))}
        </div>
      </GlassCard>
    )
  }

  if (themes.isError || !themes.data) {
    return <ErrorBanner error={themes.error} />
  }

  return (
    <div className="space-y-6">
      <GlassCard className="p-5">
        <h2 className="text-xs uppercase tracking-widest text-ink-muted">
          Tema Keşfi — küratörlü NASDAQ listeleri
        </h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {themes.data.themes.map((theme) => (
            <button
              key={theme.slug}
              onClick={() => setSlug(theme.slug === slug ? null : theme.slug)}
              className={`rounded-full border px-4 py-1.5 text-sm transition-colors ${
                theme.slug === slug
                  ? 'border-accent/60 bg-accent/10 text-accent'
                  : 'border-white/15 text-ink-muted hover:border-accent/40 hover:text-ink'
              }`}
            >
              {theme.name}
              <span className="ml-2 font-mono text-xs tabular-nums opacity-60">
                {theme.ticker_count}
              </span>
            </button>
          ))}
        </div>
      </GlassCard>

      {slug !== null && detail.isPending && (
        <GlassCard>
          <div className="space-y-3 p-6">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-9 animate-pulse rounded bg-white/5" />
            ))}
          </div>
        </GlassCard>
      )}
      {slug !== null && detail.isError && <ErrorBanner error={detail.error} />}
      {slug !== null && detail.data && <ThemeStocksTable detail={detail.data} />}

      {slug === null && (
        <p className="text-center text-xs text-ink-muted">
          Bir tema seçin — liste anlık Finnhub fiyatları ve sektör etiketleriyle
          zenginleştirilir.
        </p>
      )}

      <DisclaimerNote text={themes.data.disclaimer} />
    </div>
  )
}
