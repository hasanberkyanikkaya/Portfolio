import { request } from './client'
import type { MarketPulseResponse } from '../types/api'

export function getMarketPulse(): Promise<MarketPulseResponse> {
  return request<MarketPulseResponse>('/market-pulse')
}

export function refreshMarketPulse(): Promise<MarketPulseResponse> {
  return request<MarketPulseResponse>('/market-pulse/refresh', { method: 'POST' })
}
