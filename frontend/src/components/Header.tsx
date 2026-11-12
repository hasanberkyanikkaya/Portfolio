import { BackendStatusDot } from './BackendStatusDot'

export function Header() {
  return (
    <header className="flex items-baseline justify-between pb-6 pt-8">
      <div>
        <h1 className="font-display text-2xl font-semibold tracking-tight">
          Portfolio<span className="text-accent">.</span>
        </h1>
        <p className="mt-1 text-xs text-ink-muted">
          NASDAQ positions · live prices refresh every 15 minutes
        </p>
      </div>
      <BackendStatusDot />
    </header>
  )
}
