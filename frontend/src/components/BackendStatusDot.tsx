import { useHealth } from '../hooks/useHealth'

export function BackendStatusDot() {
  const { data, isError, isPending } = useHealth()

  const ok = !isError && data?.status === 'ok'
  const label = isPending ? 'Checking backend…' : ok ? 'Backend online' : 'Backend unreachable'

  return (
    <div className="flex items-center gap-2 text-xs text-ink-muted" title={label}>
      <span
        className={`h-2 w-2 rounded-full ${
          isPending ? 'bg-ink-muted' : ok ? 'bg-accent shadow-[0_0_6px_var(--color-accent)]' : 'bg-loss'
        }`}
      />
      {label}
    </div>
  )
}
