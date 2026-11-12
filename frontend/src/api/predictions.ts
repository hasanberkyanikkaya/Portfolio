import { request } from './client'
import type {
  PredictionsRunResponse,
  PredictionsSummaryResponse,
  TickerPredictionsResponse,
} from '../types/api'

export function getPredictionsSummary(): Promise<PredictionsSummaryResponse> {
  return request<PredictionsSummaryResponse>('/predictions')
}

export function getTickerPredictions(ticker: string): Promise<TickerPredictionsResponse> {
  return request<TickerPredictionsResponse>(`/predictions/${encodeURIComponent(ticker)}`)
}

export function runPredictions(): Promise<PredictionsRunResponse> {
  return request<PredictionsRunResponse>('/predictions/run', { method: 'POST' })
}
