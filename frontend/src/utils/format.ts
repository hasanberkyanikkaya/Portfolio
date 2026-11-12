// Display-only formatting. API Decimals stay strings; Number() is used solely
// to feed Intl.NumberFormat — no arithmetic happens client-side.

const EM_DASH = '—'

const money = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const signedMoney = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
})

const signedPct = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
  signDisplay: 'exceptZero',
})

const quantityFmt = new Intl.NumberFormat('en-US', {
  maximumFractionDigits: 6,
})

export function formatMoney(value: string | null): string {
  if (value === null) return EM_DASH
  return money.format(Number(value))
}

export function formatSignedMoney(value: string | null): string {
  if (value === null) return EM_DASH
  return signedMoney.format(Number(value))
}

export function formatPct(value: string | null): string {
  if (value === null) return EM_DASH
  return `${signedPct.format(Number(value))}%`
}

const plainPct = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

/** Unsigned percentages (weights, shares of a whole) — no leading "+". */
export function formatWeightPct(value: string | null): string {
  if (value === null) return EM_DASH
  return `${plainPct.format(Number(value))}%`
}

export function formatQuantity(value: string): string {
  return quantityFmt.format(Number(value))
}

const scoreFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })

/** 0-100 sentiment scores — whole numbers read best on a gauge. */
export function formatScore(value: string | null): string {
  if (value === null) return EM_DASH
  return scoreFmt.format(Number(value))
}

const newsDateFmt = new Intl.DateTimeFormat('en-US', {
  month: 'short',
  day: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** ISO datetime -> "Jul 8, 14:30" (viewer's local time). */
export function formatNewsDate(iso: string): string {
  return newsDateFmt.format(new Date(iso))
}

export function pnlColorClass(value: string | null): string {
  if (value === null) return 'text-ink-muted'
  const n = Number(value)
  if (n > 0) return 'text-profit'
  if (n < 0) return 'text-loss'
  return 'text-ink-muted'
}

// Full literal class strings — Tailwind v4's source scanner cannot see
// concatenated class names.
const PROFIT_BUCKETS = ['bg-profit/10', 'bg-profit/25', 'bg-profit/40', 'bg-profit/60']
const LOSS_BUCKETS = ['bg-loss/10', 'bg-loss/25', 'bg-loss/40', 'bg-loss/60']

export function heatmapBgClass(value: string | null): string {
  if (value === null) return 'bg-white/5'
  const n = Number(value)
  if (n === 0) return 'bg-white/5'
  const a = Math.abs(n)
  const bucket = a < 0.5 ? 0 : a < 1.5 ? 1 : a < 3 ? 2 : 3
  return n > 0 ? PROFIT_BUCKETS[bucket] : LOSS_BUCKETS[bucket]
}
