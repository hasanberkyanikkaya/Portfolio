import type { ReactNode } from 'react'

interface GlassCardProps {
  children: ReactNode
  className?: string
  /** SummaryCard variant: adds a soft cyan ambient glow behind the Aurora Edge. */
  glow?: boolean
}

// Frosted glass card. Every card carries the "Aurora Edge" — a 1px top edge
// lit with a cyan gradient — the signature element of the design system.
export function GlassCard({ children, className = '', glow = false }: GlassCardProps) {
  return (
    <div
      className={`relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.04] backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.35),inset_0_1px_0_rgba(255,255,255,0.06)] ${className}`}
    >
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/60 to-transparent" />
      {glow && (
        <div className="pointer-events-none absolute -inset-x-8 -top-8 h-24 bg-accent/10 blur-3xl" />
      )}
      {children}
    </div>
  )
}
