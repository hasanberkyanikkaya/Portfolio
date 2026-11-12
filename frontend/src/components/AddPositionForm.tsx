import { useState } from 'react'
import { GlassCard } from './GlassCard'
import { ErrorBanner } from './ErrorBanner'
import { useAddPosition } from '../hooks/useMutations'

const inputClass =
  'w-full rounded-lg border border-white/10 bg-white/[0.06] px-3 py-2 text-sm text-ink placeholder:text-ink-muted/60 focus:border-accent/40 focus:ring-2 focus:ring-accent/40 focus:outline-none'

export function AddPositionForm() {
  const [ticker, setTicker] = useState('')
  const [quantity, setQuantity] = useState('')
  const [purchasePrice, setPurchasePrice] = useState('')
  const mutation = useAddPosition()

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    mutation.mutate(
      { ticker: ticker.trim(), quantity, purchase_price: purchasePrice },
      {
        onSuccess: () => {
          setTicker('')
          setQuantity('')
          setPurchasePrice('')
        },
      },
    )
  }

  return (
    <GlassCard className="px-6 py-5">
      <h2 className="font-display text-sm font-semibold uppercase tracking-widest text-ink-muted">
        Add Position
      </h2>
      <form onSubmit={handleSubmit} className="mt-3 space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-[1fr_1fr_1fr_auto]">
          <input
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="Ticker (e.g. AAPL)"
            required
            maxLength={10}
            className={`${inputClass} font-mono uppercase`}
            aria-label="Ticker"
          />
          <input
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="Quantity"
            required
            type="number"
            min="0.000001"
            step="any"
            className={`${inputClass} font-mono`}
            aria-label="Quantity"
          />
          <input
            value={purchasePrice}
            onChange={(e) => setPurchasePrice(e.target.value)}
            placeholder="Purchase price ($)"
            required
            type="number"
            min="0.0001"
            step="any"
            className={`${inputClass} font-mono`}
            aria-label="Purchase price"
          />
          <button
            type="submit"
            disabled={mutation.isPending}
            className="rounded-lg border border-accent/40 bg-accent/10 px-5 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {mutation.isPending ? 'Adding…' : 'Add'}
          </button>
        </div>
        {mutation.isError && <ErrorBanner error={mutation.error} />}
      </form>
    </GlassCard>
  )
}
