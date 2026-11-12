import { request } from './client'
import type { ProtectResponse } from '../types/api'

export function getProtect(): Promise<ProtectResponse> {
  return request<ProtectResponse>('/portfolio/protect')
}

export function refreshProtect(): Promise<ProtectResponse> {
  return request<ProtectResponse>('/portfolio/protect/refresh', { method: 'POST' })
}
