// All Decimal fields arrive as JSON strings (e.g. "150.2500") for exact
// precision. Keep them as strings — never do money math in the frontend.

export type PriceStatus = 'ok' | 'unavailable'

export interface PositionWithPnL {
  id: number
  ticker: string
  quantity: string
  purchase_price: string
  purchase_date: string
  created_at: string
  cost_basis: string
  current_price: string | null
  market_value: string | null
  unrealized_pnl: string | null
  unrealized_pnl_pct: string | null
  price_status: PriceStatus
}

export interface PortfolioResponse {
  positions: PositionWithPnL[]
  total_cost_basis: string
  total_market_value: string | null
  total_unrealized_pnl: string | null
}

export interface PositionCreate {
  ticker: string
  quantity: string
  purchase_price: string
  purchase_date?: string
}

export interface PositionResponse {
  id: number
  ticker: string
  quantity: string
  purchase_price: string
  purchase_date: string
  created_at: string
}

export interface PositionCloseRequest {
  sale_price: string
  sale_date?: string
}

export interface RealizedTradeResponse {
  id: number
  ticker: string
  quantity: string
  purchase_price: string
  sale_price: string
  sale_date: string
  realized_pnl: string
  created_at: string
}

export interface RealizedTradesResponse {
  trades: RealizedTradeResponse[]
  total_realized_pnl: string
}

export interface HealthResponse {
  status: string
  database: string
}

export type RspSpySignal = 'broad_participation' | 'megacap_concentration' | 'neutral'

export interface SectorPerformance {
  symbol: string
  name: string
  daily_change_pct: string | null
  weekly_change_pct: string | null
}

export interface RspSpyComparison {
  rsp_daily_pct: string | null
  spy_daily_pct: string | null
  rsp_weekly_pct: string | null
  spy_weekly_pct: string | null
  daily_gap_pct: string | null
  weekly_gap_pct: string | null
  signal: RspSpySignal
}

export interface MaPositioning {
  symbol: string
  index: string
  close: string
  as_of: string
  ma50: string
  ma200: string
  above_ma50: boolean
  above_ma200: boolean
  pct_from_ma50: string
  pct_from_ma200: string
}

export interface MarketPulseData {
  sectors: SectorPerformance[]
  rsp_spy: RspSpyComparison | null
  ma_positioning: MaPositioning[]
}

export interface MarketPulseContent {
  text: string
  model: string
  generated_at: string
  warnings: string[]
  data: MarketPulseData
}

export interface MarketPulseResponse {
  report_date: string
  content: MarketPulseContent
  created_at: string
  updated_at: string | null
}

export type SentimentLabel =
  | 'extreme_fear'
  | 'fear'
  | 'neutral'
  | 'greed'
  | 'extreme_greed'

export interface VixComponent {
  latest_close: string
  as_of: string
  avg_252: string
  pct_vs_avg: string
  score: string
}

export interface MomentumComponent {
  spy_close: string
  as_of: string
  ma125: string
  pct_from_ma125: string
  score: string
}

export interface BreadthComponent {
  universe_size: number
  basket_size: number
  new_highs: number
  new_lows: number
  net_ratio_pct: string
  score: string
}

export interface SentimentData {
  score: string
  label: SentimentLabel
  components_used: number
  vix: VixComponent | null
  momentum: MomentumComponent | null
  breadth: BreadthComponent | null
}

export interface SentimentContent {
  text: string
  model: string
  generated_at: string
  warnings: string[]
  data: SentimentData
}

export interface SentimentResponse {
  report_date: string
  content: SentimentContent
  created_at: string
  updated_at: string | null
}

export type TechnicalLabel = 'strong' | 'weak' | 'neutral'

export interface StockTechnical {
  ticker: string
  data_status: 'ok' | 'unavailable'
  close: string | null
  as_of: string | null
  high_52w: string | null
  low_52w: string | null
  pct_from_high_52w: string | null
  pct_from_low_52w: string | null
  ma50: string | null
  ma200: string | null
  above_ma50: boolean | null
  above_ma200: boolean | null
  pct_from_ma50: string | null
  pct_from_ma200: string | null
  earnings_this_week: boolean | null
  earnings_date: string | null
  label: TechnicalLabel | null
}

export interface PortfolioTechnicalResponse {
  as_of_date: string
  stocks: StockTechnical[]
  warnings: string[]
}

export interface NewsItem {
  headline: string
  source: string | null
  url: string | null
  summary: string | null
  published_at: string
}

export interface TickerNewsResponse {
  ticker: string
  from_date: string
  to_date: string
  items: NewsItem[]
}

export interface GlossaryTerm {
  term: string
  definition: string
}

export interface GlossaryResponse {
  terms: GlossaryTerm[]
}

// --- Setups (Phase 7, cached daily report) ---------------------------------------

export type SetupRuleId = 'rsi_oversold_ma50' | 'ma200_reclaim' | 'low_rsi_divergence'

export interface SetupItem {
  ticker: string
  rule_id: SetupRuleId
  rule_name: string
  close: string
  as_of: string
  entry_zone_low: string
  entry_zone_high: string
  stop_loss: string
  rsi_14: string | null
  ma50: string | null
  ma200: string | null
  low_52w: string | null
  swing_low_20: string | null
  rationale: string
}

export interface SetupsData {
  positions_scanned: number
  setups: SetupItem[]
}

export interface SetupsContent {
  text: string
  model: string
  generated_at: string
  warnings: string[]
  data: SetupsData
}

export interface SetupsResponse {
  report_date: string
  content: SetupsContent
  created_at: string
  updated_at: string | null
}

// --- Protect (Phase 7, cached daily report) --------------------------------------

export type RiskLevel = 'low' | 'medium' | 'high'
export type RiskFlagId =
  | 'position_concentration'
  | 'sector_concentration'
  | 'low_diversification'
  | 'unknown_sectors'
export type MacroEventType = 'FOMC' | 'CPI' | 'NFP' | 'other'

export interface PositionWeight {
  ticker: string
  sector: string
  value: string
  weight_pct: string
  weight_basis: 'market' | 'cost'
}

export interface SectorWeight {
  sector: string
  weight_pct: string
  tickers: string[]
}

export interface RiskFlag {
  flag_id: RiskFlagId
  detail: string
  tickers: string[]
}

export interface MacroEvent {
  date: string
  event_type: MacroEventType
  title: string
  approximate: boolean
  source: 'static' | 'finnhub'
  sensitive_sectors: string[]
  affected_tickers: string[]
}

export interface ProtectData {
  position_count: number
  total_value: string | null
  risk_score: number
  risk_level: RiskLevel
  positions: PositionWeight[]
  sectors: SectorWeight[]
  flags: RiskFlag[]
  macro_events: MacroEvent[]
}

export interface ProtectContent {
  text: string
  model: string
  generated_at: string
  warnings: string[]
  data: ProtectData
}

export interface ProtectResponse {
  report_date: string
  content: ProtectContent
  created_at: string
  updated_at: string | null
}

// --- Predictions (Phase 8, pure data — no Claude) ----------------------------------

export type PredictionAlgorithm = 'trend_ma' | 'rsi_reversion' | 'swing_breakout'
export type PredictionDirection = 'up' | 'down'
export type PredictionStatus = 'pending' | 'correct' | 'incorrect' | 'expired'

export interface PredictionItem {
  id: number
  ticker: string
  algorithm: PredictionAlgorithm
  algorithm_name: string
  prediction_date: string
  predicted_direction: PredictionDirection
  price_at_prediction: string
  horizon_days: number
  status: PredictionStatus
  evaluation_date: string | null
  price_at_evaluation: string | null
  actual_return_pct: string | null
  created_at: string
}

export interface AlgorithmStats {
  algorithm: PredictionAlgorithm
  algorithm_name: string
  total: number
  correct: number
  incorrect: number
  pending: number
  expired: number
  accuracy_pct: string | null
}

export interface PredictionsSummaryResponse {
  stats: AlgorithmStats[]
  predictions: PredictionItem[]
  disclaimer: string
}

export interface TickerPredictionsResponse {
  ticker: string
  stats: AlgorithmStats[]
  predictions: PredictionItem[]
  disclaimer: string
}

export interface PredictionsRunResponse {
  created: number
  evaluated: number
  expired: number
  warnings: string[]
  disclaimer: string
}

// --- Risk profile (Phase 8) ---------------------------------------------------------

export type RiskHorizon = 'short' | 'medium' | 'long'
export type LossTolerance = 'sell' | 'hold' | 'buy_more'
export type CapitalShare = 'large' | 'moderate' | 'small'
export type InvestorProfile = 'conservative' | 'balanced' | 'aggressive'

export interface RiskProfileIn {
  horizon: RiskHorizon
  loss_tolerance: LossTolerance
  capital_share: CapitalShare
}

export interface RiskProfileOut {
  horizon: RiskHorizon
  loss_tolerance: LossTolerance
  capital_share: CapitalShare
  score: number
  profile: InvestorProfile
  protect_risk_level: RiskLevel | null
  mismatch: boolean | null
  mismatch_detail: string | null
  updated_at: string | null
  disclaimer: string
}

// --- Themes (Phase 8, curated static lists) -------------------------------------------

export interface ThemeSummary {
  slug: string
  name: string
  description: string
  ticker_count: number
}

export interface ThemesListResponse {
  themes: ThemeSummary[]
  disclaimer: string
}

export interface ThemeStock {
  ticker: string
  price: string | null
  percent_change: string | null
  industry: string | null
  price_status: 'ok' | 'unavailable'
}

export interface ThemeDetailResponse {
  slug: string
  name: string
  description: string
  stocks: ThemeStock[]
  warnings: string[]
  disclaimer: string
}
