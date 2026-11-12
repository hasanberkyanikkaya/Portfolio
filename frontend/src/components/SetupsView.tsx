import { GlassCard } from './GlassCard'
import { EmptyState } from './EmptyState'
import { ErrorBanner } from './ErrorBanner'
import { useSetups } from '../hooks/useSetups'
import { formatMoney } from '../utils/format'
import type { SetupItem } from '../types/api'

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-widest text-ink-muted">{label}</div>
      <div className="mt-0.5 font-mono text-sm tabular-nums">{value}</div>
    </div>
  )
}

function SetupCard({ setup }: { setup: SetupItem }) {
  return (
    <GlassCard className="p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="font-display text-lg font-semibold">{setup.ticker}</span>
          <span className="rounded-full border border-accent/40 px-2.5 py-0.5 text-xs text-accent">
            {setup.rule_name}
          </span>
        </div>
        <span className="font-mono text-xs tabular-nums text-ink-muted">{setup.as_of}</span>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Metric
          label="Entry zone"
          value={`${formatMoney(setup.entry_zone_low)} – ${formatMoney(setup.entry_zone_high)}`}
        />
        <Metric label="Stop-loss" value={formatMoney(setup.stop_loss)} />
        <Metric label="Close" value={formatMoney(setup.close)} />
        <Metric label="RSI(14)" value={setup.rsi_14 ?? '—'} />
      </div>
      <p className="mt-4 text-xs leading-relaxed text-ink-muted">{setup.rationale}</p>
    </GlassCard>
  )
}

export function SetupsView() {
  const { data, isPending, isError, error } = useSetups()

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
    return (
      <GlassCard>
        <EmptyState message="No Setups report yet — it is generated after each market close (17:00 ET)." />
      </GlassCard>
    )
  }

  if (isError || !data) {
    return <ErrorBanner error={error} />
  }

  const { content } = data
  const { setups, positions_scanned } = content.data
  return (
    <div className="space-y-6">
      {setups.length === 0 ? (
        <GlassCard>
          <EmptyState
            message={
              positions_scanned === 0
                ? 'The portfolio is empty — there is nothing to scan yet.'
                : `No setups detected today across ${positions_scanned} scanned holding(s). An empty scan is a valid result — the rules only fire when their conditions are actually met.`
            }
          />
        </GlassCard>
      ) : (
        setups.map((setup) => <SetupCard key={setup.ticker} setup={setup} />)
      )}
      <GlassCard className="p-6">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="text-xs uppercase tracking-widest text-ink-muted">
            Setups Commentary
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
