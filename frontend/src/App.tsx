import { useState } from 'react'
import { Header } from './components/Header'
import { SummaryCard } from './components/SummaryCard'
import { Tabs, type TabId } from './components/Tabs'
import { AddPositionForm } from './components/AddPositionForm'
import { PositionsTable } from './components/PositionsTable'
import { RealizedTable } from './components/RealizedTable'
import { MarketPulseView } from './components/MarketPulseView'
import { SentimentView } from './components/SentimentView'
import { SetupsView } from './components/SetupsView'
import { ProtectView } from './components/ProtectView'
import { PredictionsView } from './components/PredictionsView'
import { ThemesView } from './components/ThemesView'
import { ClosePositionDialog } from './components/ClosePositionDialog'
import { NewsDialog } from './components/NewsDialog'
import type { PositionWithPnL } from './types/api'

export default function App() {
  const [tab, setTab] = useState<TabId>('portfolio')
  const [closeTarget, setCloseTarget] = useState<PositionWithPnL | null>(null)
  const [newsTarget, setNewsTarget] = useState<PositionWithPnL | null>(null)

  return (
    <div className="mx-auto max-w-5xl px-4 pb-16 sm:px-6">
      <Header />
      <div className="space-y-6">
        <SummaryCard />
        <Tabs active={tab} onChange={setTab} />
        {tab === 'portfolio' && (
          <>
            <AddPositionForm />
            <PositionsTable onClose={setCloseTarget} onNews={setNewsTarget} />
          </>
        )}
        {tab === 'realized' && <RealizedTable />}
        {tab === 'pulse' && <MarketPulseView />}
        {tab === 'sentiment' && <SentimentView />}
        {tab === 'setups' && <SetupsView />}
        {tab === 'protect' && <ProtectView />}
        {tab === 'predictions' && <PredictionsView />}
        {tab === 'discover' && <ThemesView />}
      </div>
      {closeTarget && (
        <ClosePositionDialog
          key={closeTarget.id}
          position={closeTarget}
          onDone={() => setCloseTarget(null)}
        />
      )}
      {newsTarget && (
        <NewsDialog
          key={newsTarget.ticker}
          ticker={newsTarget.ticker}
          onClose={() => setNewsTarget(null)}
        />
      )}
      <footer className="mt-10 text-center text-xs text-ink-muted/70">
        This is not investment advice — for educational purposes only.
      </footer>
    </div>
  )
}
