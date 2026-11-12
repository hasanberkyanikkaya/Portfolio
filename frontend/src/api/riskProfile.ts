import { request } from './client'
import type { RiskProfileIn, RiskProfileOut } from '../types/api'

export function getRiskProfile(): Promise<RiskProfileOut> {
  return request<RiskProfileOut>('/risk-profile')
}

export function submitRiskProfile(body: RiskProfileIn): Promise<RiskProfileOut> {
  return request<RiskProfileOut>('/risk-profile', {
    method: 'POST',
    body: JSON.stringify(body),
  })
}
