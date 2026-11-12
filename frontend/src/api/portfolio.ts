import { request } from './client'
import type { PortfolioTechnicalResponse, TickerNewsResponse } from '../types/api'

export function getPortfolioTechnical(): Promise<PortfolioTechnicalResponse> {
  return request<PortfolioTechnicalResponse>('/portfolio/technical')
}

export function getTickerNews(ticker: string): Promise<TickerNewsResponse> {
  return request<TickerNewsResponse>(`/portfolio/${encodeURIComponent(ticker)}/news`)
}
