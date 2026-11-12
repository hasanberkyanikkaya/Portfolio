import { useState } from 'react'
import { GlassCard } from './GlassCard'
import { EmptyState } from './EmptyState'
import { ErrorBanner } from './ErrorBanner'
import { DisclaimerNote } from './DisclaimerNote'
import { usePredictions, useTickerPredictions } from '../hooks/usePredictions'
import { useRunPredictions } from '../hooks/useMutations'
import { formatMoney, formatPct, formatWeightPct, pnlColorClass } from '../utils/format'
import type { AlgorithmStats, PredictionItem, PredictionStatus } from '../types/api'

const STATUS_LABELS: Record<PredictionStatus, string> = {
  pending: 'beklemede',
  correct: 'doğru',
  incorrect: 'yanlış',
  expired: 'değerlendirilemedi',
}

// Accuracy is a track record, not P&L — it stays monochrome + cyan per the
// color rule. Only actual_return_pct (market performance) gets green/red.
const STATUS_PILL: Record<PredictionStatus, string> = {
  pending: 'border-white/15 text-ink-muted',
  correct: 'border-accent/40 text-accent',
  incorrect: 'border-white/15 text-ink',
  expired: 'border-white/10 text-ink-muted/60',
}

function StatusPill({ status }: { status: PredictionStatus }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider ${STATUS_PILL[status]}`}
    >
      {STATUS_LABELS[status]}
    </span>
  )
}

function AccuracyBar({ pct }: { pct: string | null }) {
  const width = pct === null ? 0 : Math.min(Number(pct), 100)
  return (
    <div className="h-1.5 w-full rounded-full bg-white/10">
      <div className="h-1.5 rounded-full bg-accent/60" style={{ width: `${width}%` }} />
    </div>
  )
}

function StatsCard({ stats }: { stats: AlgorithmStats }) {
  const decided = stats.correct + stats.incorrect
  return (
    <GlassCard className="p-5">
      <div className="text-xs uppercase tracking-widest text-ink-muted">
        {stats.algorithm_name}
      </div>
      <div className="mt-3 flex items-baseline gap-2">
        <span className="font-mono text-3xl font-semibold tabular-nums">
          {stats.accuracy_pct === null ? '—' : formatWeightPct(stats.accuracy_pct)}
        </span>
        <span className="text-xs text-ink-muted">
          {decided > 0 ? `${stats.correct}/${decided} doğru` : 'henüz sonuç yok'}
        </span>
      </div>
      <div className="mt-3">
        <AccuracyBar pct={stats.accuracy_pct} />
      </div>
      <div className="mt-3 flex gap-4 font-mono text-xs tabular-nums text-ink-muted">
        <span>{stats.pending} beklemede</span>
        <span>{stats.expired} süresi doldu</span>
        <span>{stats.total} toplam</span>
      </div>
    </GlassCard>
  )
}

function DirectionArrow({ direction }: { direction: 'up' | 'down' }) {
  return (
    <span className="font-mono text-sm">
      {direction === 'up' ? '↑ yükseliş' : '↓ düşüş'}
    </span>
  )
}

function PredictionsTable({ predictions }: { predictions: PredictionItem[] }) {
  return (
    <GlassCard className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/10 text-left text-[10px] uppercase tracking-widest text-ink-muted">
            <th className="px-4 py-3 font-medium">Date</th>
            <th className="px-4 py-3 font-medium">Ticker</th>
            <th className="px-4 py-3 font-medium">Algorithm</th>
            <th className="px-4 py-3 font-medium">Direction</th>
            <th className="px-4 py-3 text-right font-medium">Entry</th>
            <th className="px-4 py-3 text-right font-medium">Eval</th>
            <th className="px-4 py-3 text-right font-medium">Return</th>
            <th className="px-4 py-3 text-right font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {predictions.map((p) => (
            <tr key={p.id} className="border-b border-white/5 last:border-0">
              <td className="px-4 py-3 font-mono text-xs tabular-nums text-ink-muted">
                {p.prediction_date}
              </td>
              <td className="px-4 py-3 font-display font-semibold">{p.ticker}</td>
              <td className="px-4 py-3 text-xs text-ink-muted">{p.algorithm_name}</td>
              <td className="px-4 py-3">
                <DirectionArrow direction={p.predicted_direction} />
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums">
                {formatMoney(p.price_at_prediction)}
              </td>
              <td className="px-4 py-3 text-right font-mono tabular-nums">
                {formatMoney(p.price_at_evaluation)}
              </td>
              <td
                className={`px-4 py-3 text-right font-mono tabular-nums ${pnlColorClass(p.actual_return_pct)}`}
              >
                {formatPct(p.actual_return_pct)}
              </td>
              <td className="px-4 py-3 text-right">
                <StatusPill status={p.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </GlassCard>
  )
}

const selectClass =
  'rounded-lg border border-white/10 bg-white/[0.06] px-3 py-1.5 text-sm text-ink focus:border-accent/40 focus:ring-2 focus:ring-accent/40 focus:outline-none'

export function PredictionsView() {
  const [ticker, setTicker] = useState<string | null>(null)
  const summary = usePredictions()
  const tickerQuery = useTickerPredictions(ticker)
  const runMutation = useRunPredictions()

  if (summary.isPending) {
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

  if (summary.isError || !summary.data) {
    return <ErrorBanner error={summary.error} />
  }

  const active = ticker !== null && tickerQuery.data ? tickerQuery.data : summary.data
  const tickers = [...new Set(summary.data.predictions.map((p) => p.ticker))].sort()

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 className="font-display text-sm font-semibold uppercase tracking-widest text-ink-muted">
            Prediction Track Record
          </h2>
          {tickers.length > 0 && (
            <select
              value={ticker ?? ''}
              onChange={(e) => setTicker(e.target.value === '' ? null : e.target.value)}
              className={selectClass}
              aria-label="Ticker filter"
            >
              <option value="">All tickers</option>
              {tickers.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          )}
        </div>
        <button
          onClick={() => runMutation.mutate()}
          disabled={runMutation.isPending}
          className="rounded-lg border border-accent/40 bg-accent/10 px-5 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {runMutation.isPending ? 'Çalışıyor…' : 'Şimdi çalıştır'}
        </button>
      </div>

      {runMutation.isError && <ErrorBanner error={runMutation.error} />}
      {runMutation.isSuccess && (
        <p className="text-xs text-ink-muted">
          Son çalıştırma: {runMutation.data.created} yeni tahmin,{' '}
          {runMutation.data.evaluated} değerlendirildi, {runMutation.data.expired} süresi
          doldu.
        </p>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {active.stats.map((s) => (
          <StatsCard key={s.algorithm} stats={s} />
        ))}
      </div>

      {ticker !== null && tickerQuery.isError && tickerQuery.error.status === 404 ? (
        <GlassCard>
          <EmptyState message={`No predictions recorded for ${ticker} yet.`} />
        </GlassCard>
      ) : active.predictions.length === 0 ? (
        <GlassCard>
          <EmptyState message="No predictions yet — they are logged every trading day at 17:10 ET (or use the run button above)." />
        </GlassCard>
      ) : (
        <PredictionsTable predictions={active.predictions} />
      )}

      <DisclaimerNote text={active.disclaimer} />
    </div>
  )
}
