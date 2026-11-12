import { useState } from 'react'
import { GlassCard } from './GlassCard'
import { ErrorBanner } from './ErrorBanner'
import { DisclaimerNote } from './DisclaimerNote'
import { useRiskProfile } from '../hooks/useRiskProfile'
import { useSubmitRiskProfile } from '../hooks/useMutations'
import type {
  CapitalShare,
  InvestorProfile,
  LossTolerance,
  RiskHorizon,
  RiskLevel,
  RiskProfileIn,
} from '../types/api'

const PROFILE_LABELS: Record<InvestorProfile, string> = {
  conservative: 'Temkinli',
  balanced: 'Dengeli',
  aggressive: 'Agresif',
}

const RISK_LEVEL_LABELS: Record<RiskLevel, string> = {
  low: 'düşük',
  medium: 'orta',
  high: 'yüksek',
}

const HORIZON_OPTIONS: { value: RiskHorizon; label: string }[] = [
  { value: 'short', label: '1 yıldan az' },
  { value: 'medium', label: '1–5 yıl' },
  { value: 'long', label: '5 yıldan fazla' },
]

const LOSS_OPTIONS: { value: LossTolerance; label: string }[] = [
  { value: 'sell', label: 'Satarım' },
  { value: 'hold', label: 'Beklerim' },
  { value: 'buy_more', label: 'Alım yaparım' },
]

const CAPITAL_OPTIONS: { value: CapitalShare; label: string }[] = [
  { value: 'large', label: 'Birikimimin büyük kısmı' },
  { value: 'moderate', label: 'Önemli ama kritik değil' },
  { value: 'small', label: 'Kaybını göze alabilirim' },
]

function ChoiceGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { value: T; label: string }[]
  value: T | null
  onChange: (value: T) => void
}) {
  return (
    <div>
      <div className="text-xs uppercase tracking-widest text-ink-muted">{label}</div>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
              value === option.value
                ? 'border-accent/60 bg-accent/10 text-accent'
                : 'border-white/10 bg-white/[0.06] text-ink-muted hover:border-accent/40 hover:text-ink'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  )
}

function Questionnaire({ onDone }: { onDone: () => void }) {
  const [horizon, setHorizon] = useState<RiskHorizon | null>(null)
  const [lossTolerance, setLossTolerance] = useState<LossTolerance | null>(null)
  const [capitalShare, setCapitalShare] = useState<CapitalShare | null>(null)
  const mutation = useSubmitRiskProfile()

  const complete = horizon !== null && lossTolerance !== null && capitalShare !== null

  function handleSubmit() {
    if (!complete) return
    const body: RiskProfileIn = {
      horizon: horizon!,
      loss_tolerance: lossTolerance!,
      capital_share: capitalShare!,
    }
    mutation.mutate(body, { onSuccess: onDone })
  }

  return (
    <div className="mt-4 space-y-4">
      <ChoiceGroup
        label="Yatırım ufkunuz?"
        options={HORIZON_OPTIONS}
        value={horizon}
        onChange={setHorizon}
      />
      <ChoiceGroup
        label="Portföyünüz %20 düşerse ne yaparsınız?"
        options={LOSS_OPTIONS}
        value={lossTolerance}
        onChange={setLossTolerance}
      />
      <ChoiceGroup
        label="Bu paranın birikimlerinizdeki yeri?"
        options={CAPITAL_OPTIONS}
        value={capitalShare}
        onChange={setCapitalShare}
      />
      <button
        onClick={handleSubmit}
        disabled={!complete || mutation.isPending}
        className="rounded-lg border border-accent/40 bg-accent/10 px-5 py-2 text-sm font-medium text-accent transition-colors hover:bg-accent/20 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {mutation.isPending ? 'Kaydediliyor…' : 'Profili kaydet'}
      </button>
      {mutation.isError && <ErrorBanner error={mutation.error} />}
    </div>
  )
}

export function RiskProfileCard() {
  const { data, isPending, isError, error } = useRiskProfile()
  const [editing, setEditing] = useState(false)

  if (isPending) {
    return (
      <GlassCard>
        <div className="space-y-3 p-6">
          {[0, 1].map((i) => (
            <div key={i} className="h-9 animate-pulse rounded bg-white/5" />
          ))}
        </div>
      </GlassCard>
    )
  }

  const notSubmitted = isError && error.status === 404
  if (isError && !notSubmitted) {
    return <ErrorBanner error={error} />
  }

  const showForm = notSubmitted || editing || !data

  return (
    <GlassCard className="p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-xs uppercase tracking-widest text-ink-muted">
          Risk Profili
        </h2>
        {!showForm && (
          <button
            onClick={() => setEditing(true)}
            className="text-xs text-accent hover:underline"
          >
            Yeniden doldur
          </button>
        )}
      </div>

      {showForm ? (
        <Questionnaire onDone={() => setEditing(false)} />
      ) : (
        <div className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center gap-4">
            <span className="rounded-full border border-accent/40 px-3 py-1 text-sm text-accent">
              {PROFILE_LABELS[data.profile]}
            </span>
            <span className="font-mono text-xs tabular-nums text-ink-muted">
              skor {data.score}/9
            </span>
            {data.protect_risk_level !== null && (
              <span className="text-xs text-ink-muted">
                Portföy riski (Protect):{' '}
                <span className="uppercase tracking-wider">
                  {RISK_LEVEL_LABELS[data.protect_risk_level]}
                </span>
              </span>
            )}
          </div>

          {data.mismatch === true && data.mismatch_detail !== null && (
            <div className="rounded-lg border border-accent/40 bg-accent/5 px-4 py-3 text-sm leading-relaxed">
              {data.mismatch_detail}
            </div>
          )}
          {data.mismatch === false && (
            <p className="text-sm text-ink-muted">
              Portföyün mevcut risk seviyesi profilinizle uyumlu.
            </p>
          )}
          {data.mismatch === null && (
            <p className="text-sm text-ink-muted">
              Karşılaştırma için henüz bir Protect raporu yok — rapor oluştuğunda
              profiliniz portföy riskiyle otomatik karşılaştırılır.
            </p>
          )}

          <DisclaimerNote text={data.disclaimer} />
        </div>
      )}
    </GlassCard>
  )
}
