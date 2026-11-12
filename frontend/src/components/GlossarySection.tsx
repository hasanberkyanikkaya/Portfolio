import { useState } from 'react'
import { GlassCard } from './GlassCard'
import { ErrorBanner } from './ErrorBanner'
import { useGlossary } from '../hooks/useGlossary'

// Collapsible educational glossary. The static /glossary payload is fetched
// lazily on first open and cached for the whole session.
export function GlossarySection() {
  const [open, setOpen] = useState(false)
  const { data, isPending, isError, error } = useGlossary(open)

  return (
    <GlassCard className="px-6 py-5">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between text-left"
      >
        <h2 className="text-xs uppercase tracking-widest text-ink-muted">
          Glossary — what do these terms mean?
        </h2>
        <span className="text-xs text-accent">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open && (
        <div className="mt-4 space-y-4">
          {isPending && (
            <div className="space-y-3">
              {[0, 1, 2].map((i) => (
                <div key={i} className="h-9 animate-pulse rounded bg-white/5" />
              ))}
            </div>
          )}
          {isError && <ErrorBanner error={error} />}
          {data?.terms.map(({ term, definition }) => (
            <div key={term}>
              <h3 className="font-display text-sm font-semibold tracking-wide">{term}</h3>
              <p className="mt-1 text-sm leading-relaxed text-ink-muted">{definition}</p>
            </div>
          ))}
        </div>
      )}
    </GlassCard>
  )
}
