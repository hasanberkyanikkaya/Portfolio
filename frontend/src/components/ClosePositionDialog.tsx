import { useState } from 'react'
import { ErrorBanner } from './ErrorBanner'
import { useClosePosition } from '../hooks/useMutations'
import { formatMoney, formatQuantity } from '../utils/format'
import type { PositionWithPnL } from '../types/api'

const inputClass =
  'w-full rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-ink placeholder:text-ink-muted/60 focus:border-accent/40 focus:ring-2 focus:ring-accent/40 focus:outline-none font-mono'

interface ClosePositionDialogProps {
  position: PositionWithPnL
  onDone: () => void
}

export function ClosePositionDialog({ position, onDone }: ClosePositionDialogProps) {
  const [salePrice, setSalePrice] = useState(
    position.current_price !== null ? Number(position.current_price).toFixed(2) : '',
  )
  const mutation = useClosePosition()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    mutation.mutate(
      { id: position.id, body: { sale_price: salePrice } },
      { onSuccess: onDone },
    )
  }

  function handleBackdrop() {
    if (!mutation.isPending) onDone()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-void/70 backdrop-blur-sm"
      onClick={handleBackdrop}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-sm overflow-hidden rounded-2xl border border-white/10 bg-deep-navy/90 p-6 shadow-[0_8px_32px_rgba(0,0,0,0.5)] backdrop-blur-xl"
        role="dialog"
        aria-modal="true"
        aria-label={`Close position ${position.ticker}`}
      >
        <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/60 to-transparent" />
        <h2 className="font-display text-lg font-semibold">
          Close <span className="text-accent">{position.ticker}</span>
        </h2>
        <p className="mt-1 text-sm text-ink-muted">
          {formatQuantity(position.quantity)} shares · bought at{' '}
          <span className="font-mono tabular-nums">{formatMoney(position.purchase_price)}</span>
        </p>
        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <label className="block text-xs uppercase tracking-widest text-ink-muted">
            Sale price ($)
            <input
              value={salePrice}
              onChange={(e) => setSalePrice(e.target.value)}
              required
              autoFocus
              type="number"
              min="0.0001"
              step="any"
              className={`${inputClass} mt-1.5`}
            />
          </label>
          {mutation.isError && <ErrorBanner error={mutation.error} />}
          <div className="flex justify-end gap-2 pt-1">
            <button
              type="button"
              onClick={onDone}
              disabled={mutation.isPending}
              className="rounded-lg border border-white/10 bg-white/[0.06] px-4 py-2 text-sm text-ink-muted transition-colors hover:text-ink disabled:opacity-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-lg border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {mutation.isPending ? 'Closing…' : 'Confirm close'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
