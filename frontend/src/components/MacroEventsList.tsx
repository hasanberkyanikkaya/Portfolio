import { GlassCard } from './GlassCard'
import type { MacroEvent } from '../types/api'

function Chip({ text }: { text: string }) {
  return (
    <span className="rounded-full border border-accent/30 px-2 py-0.5 text-[10px] text-accent/90">
      {text}
    </span>
  )
}

export function MacroEventsList({ events }: { events: MacroEvent[] }) {
  return (
    <GlassCard className="p-6">
      <h2 className="text-xs uppercase tracking-widest text-ink-muted">
        Macro events — next 7 days
      </h2>

      {events.length === 0 ? (
        <p className="mt-3 text-sm text-ink-muted">
          No key macro events in the next 7 days.
        </p>
      ) : (
        <ul className="mt-4 space-y-4">
          {events.map((event) => (
            <li key={`${event.date}-${event.title}`}>
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="font-mono text-sm tabular-nums text-ink-muted">
                  {event.approximate ? '~' : ''}
                  {event.date}
                </span>
                <span className="text-sm">{event.title}</span>
                {event.approximate && (
                  <span className="text-xs text-ink-muted">(approximate date)</span>
                )}
              </div>
              {event.affected_tickers.length > 0 && (
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                  <span className="text-xs text-ink-muted">Sensitive:</span>
                  {event.sensitive_sectors.map((sector) => (
                    <Chip key={sector} text={sector} />
                  ))}
                  {event.affected_tickers.map((ticker) => (
                    <Chip key={ticker} text={ticker} />
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </GlassCard>
  )
}
