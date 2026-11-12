import { GlassCard } from './GlassCard'
import type { SentimentLabel } from '../types/api'
import { formatScore } from '../utils/format'

// Precomputed backend labels get Turkish display text (same pattern as the
// RSP/SPY signal badge).
const LABEL_TEXT: Record<SentimentLabel, string> = {
  extreme_fear: 'Aşırı Korku',
  fear: 'Korku',
  neutral: 'Nötr',
  greed: 'Açgözlülük',
  extreme_greed: 'Aşırı Açgözlülük',
}

interface SentimentGaugeProps {
  score: string
  label: SentimentLabel
  componentsUsed: number
}

// 0-100 fear & greed dial. Deliberately cyan, not a red→green ramp: the design
// system reserves green/red for values where green = gain, and "greed" is a
// risk signal, not a gain — the label text carries the interpretation.
export function SentimentGauge({ score, label, componentsUsed }: SentimentGaugeProps) {
  const value = Math.min(Math.max(Number(score), 0), 100)
  const arc = 'M 20 110 A 90 90 0 0 1 200 110'

  return (
    <GlassCard glow className="px-6 py-5">
      <h2 className="text-xs uppercase tracking-widest text-ink-muted">
        Fear &amp; Greed Score
      </h2>
      <div className="mt-2 flex flex-col items-center">
        <div className="relative w-full max-w-[280px]">
          <svg viewBox="0 0 220 120" className="w-full" role="img" aria-label={`Sentiment score ${formatScore(score)} of 100`}>
            <path
              d={arc}
              className="stroke-white/10"
              strokeWidth={12}
              fill="none"
              strokeLinecap="round"
            />
            {value > 0 && (
              <path
                d={arc}
                className="stroke-accent"
                strokeWidth={12}
                fill="none"
                strokeLinecap="round"
                pathLength={100}
                strokeDasharray={`${value} 100`}
              />
            )}
            <text x="20" y="119" textAnchor="middle" className="fill-ink-muted font-mono text-[9px]">0</text>
            <text x="110" y="14" textAnchor="middle" className="fill-ink-muted font-mono text-[9px]">50</text>
            <text x="200" y="119" textAnchor="middle" className="fill-ink-muted font-mono text-[9px]">100</text>
          </svg>
          <div className="absolute inset-x-0 bottom-0 text-center">
            <div className="font-mono text-4xl font-semibold tabular-nums">
              {formatScore(score)}
            </div>
          </div>
        </div>
        <span className="mt-3 rounded-full border border-accent/30 bg-accent/10 px-3 py-1 text-xs text-accent">
          {LABEL_TEXT[label]}
        </span>
        <p className="mt-2 text-xs text-ink-muted">
          0 = extreme fear · 100 = extreme greed
          {componentsUsed < 3 && ` · based on ${componentsUsed} of 3 components`}
        </p>
      </div>
    </GlassCard>
  )
}
