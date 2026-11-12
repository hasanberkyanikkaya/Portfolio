import { request } from './client'
import type {
  HealthResponse,
  PortfolioResponse,
  PositionCloseRequest,
  PositionCreate,
  PositionResponse,
  RealizedTradeResponse,
  RealizedTradesResponse,
} from '../types/api'

export function getPositions(): Promise<PortfolioResponse> {
  return request<PortfolioResponse>('/positions')
}

export function createPosition(body: PositionCreate): Promise<PositionResponse> {
  return request<PositionResponse>('/positions', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function closePosition(
  id: number,
  body: PositionCloseRequest,
): Promise<RealizedTradeResponse> {
  return request<RealizedTradeResponse>(`/positions/${id}/close`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function deletePosition(id: number): Promise<void> {
  return request<void>(`/positions/${id}`, { method: 'DELETE' })
}

export function getRealized(): Promise<RealizedTradesResponse> {
  return request<RealizedTradesResponse>('/positions/realized')
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}
