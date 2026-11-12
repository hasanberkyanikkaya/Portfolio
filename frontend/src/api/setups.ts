import { request } from './client'
import type { SetupsResponse } from '../types/api'

export function getSetups(): Promise<SetupsResponse> {
  return request<SetupsResponse>('/portfolio/setups')
}

export function refreshSetups(): Promise<SetupsResponse> {
  return request<SetupsResponse>('/portfolio/setups/refresh', { method: 'POST' })
}
