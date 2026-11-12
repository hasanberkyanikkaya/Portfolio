import { request } from './client'
import type { GlossaryResponse } from '../types/api'

export function getGlossary(): Promise<GlossaryResponse> {
  return request<GlossaryResponse>('/glossary')
}
