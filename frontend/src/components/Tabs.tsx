export type TabId =
  | 'portfolio'
  | 'realized'
  | 'pulse'
  | 'sentiment'
  | 'setups'
  | 'protect'
  | 'predictions'
  | 'discover'

interface TabsProps {
  active: TabId
  onChange: (tab: TabId) => void
}

const TABS: { id: TabId; label: string }[] = [
  { id: 'portfolio', label: 'Portfolio' },
  { id: 'realized', label: 'Realized P&L' },
  { id: 'pulse', label: 'Market Pulse' },
  { id: 'sentiment', label: 'Sentiment' },
  { id: 'setups', label: 'Setups' },
  { id: 'protect', label: 'Protect' },
  { id: 'predictions', label: 'Predictions' },
  { id: 'discover', label: 'Discover' },
]

export function Tabs({ active, onChange }: TabsProps) {
  return (
    <nav className="flex gap-6 border-b border-white/10">
      {TABS.map(({ id, label }) => (
        <button
          key={id}
          onClick={() => onChange(id)}
          className={`relative pb-2 text-sm transition-colors ${
            active === id ? 'text-ink' : 'text-ink-muted hover:text-ink'
          }`}
        >
          {label}
          {active === id && (
            // Active-tab underline reuses the Aurora Edge gradient.
            <span className="absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-transparent via-accent/60 to-transparent" />
          )}
        </button>
      ))}
    </nav>
  )
}
