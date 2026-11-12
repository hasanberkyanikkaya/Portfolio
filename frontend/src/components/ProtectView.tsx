import { GlassCard } from './GlassCard'
import { EmptyState } from './EmptyState'
import { ErrorBanner } from './ErrorBanner'
import { ConcentrationTable } from './ConcentrationTable'
import { MacroEventsList } from './MacroEventsList'
import { RiskProfileCard } from './RiskProfileCard'
import { useProtect } from '../hooks/useProtect'
import type { RiskFlag, RiskLevel } from '../types/api'

// Design rule: green/red are reserved for P&L / market performance. A risk
// badge is neither, so it stays monochrome + a cyan segment meter (the single
// decorative accent), like the sentiment gauge.
const LEVEL_SEGMENTS: Record<RiskLevel, number> = { low: 1, medium: 2, high: 3 }

function RiskMeter({ level }: { level: RiskLevel }) {
  const filled = LEVEL_SEGMENTS[level]
  return (
    <div className="flex gap-1.5">
      {[1, 2, 3].map((segment) => (
        <span
          key={segment}
          className={`h-1.5 w-8 rounded-full ${segment <= filled ? 'bg-accent' : 'bg-white/10'}`}
        />
      ))}
    </div>
  )
}

function RiskSummary({
  score,
  level,
  flags,
}: {
  score: number
  level: RiskLevel
  flags: RiskFlag[]
}) {
  return (
    <GlassCard glow className="p-6">
      <h2 className="text-xs uppercase tracking-widest text-ink-muted">Portfolio risk</h2>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <span className="font-mono text-4xl font-semibold tabular-nums">{score}</span>
        <div className="space-y-1.5">
          <span className="rounded-full border border-white/15 px-3 py-1 text-xs uppercase tracking-widest">
            {level}
          </span>
          <RiskMeter level={level} />
        </div>
      </div>
      {flags.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {flags.map((flag) => (
            <li key={flag.flag_id} className="text-sm text-ink-muted">
              <span className="mr-2 text-accent">•</span>
              {flag.detail}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-ink-muted">
          The rule-based checks found no concentration warnings.
        </p>
      )}
    </GlassCard>
  )
}

export function ProtectView() {
  const { data, isPending, isError, error } = useProtect()

  if (isPending) {
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

  if (isError && error.status === 404) {
    // The questionnaire is still useful without a Protect report — the
    // comparison simply activates once the first report exists.
    return (
      <div className="space-y-6">
        <GlassCard>
          <EmptyState message="No Protect report yet — it is generated after each market close (17:05 ET)." />
        </GlassCard>
        <RiskProfileCard />
      </div>
    )
  }

  if (isError || !data) {
    return <ErrorBanner error={error} />
  }

  const { content } = data
  const { data: report } = content
  return (
    <div className="space-y-6">
      <RiskSummary
        score={report.risk_score}
        level={report.risk_level}
        flags={report.flags}
      />
      <RiskProfileCard />
      {report.position_count === 0 ? (
        <GlassCard>
          <EmptyState message="The portfolio is empty — there is no position risk to assess yet." />
        </GlassCard>
      ) : (
        <ConcentrationTable positions={report.positions} sectors={report.sectors} />
      )}
      <MacroEventsList events={report.macro_events} />
      <GlassCard className="p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xs uppercase tracking-widest text-ink-muted">
            Protect Commentary
          </h2>
          <span className="font-mono text-xs tabular-nums text-ink-muted">
            {data.report_date}
          </span>
        </div>
        <p className="mt-3 whitespace-pre-line text-sm leading-relaxed">{content.text}</p>
        {content.warnings.length > 0 && (
          <p className="mt-3 text-xs text-ink-muted">
            Some data was unavailable: {content.warnings.join(', ')}
          </p>
        )}
      </GlassCard>
    </div>
  )
}
