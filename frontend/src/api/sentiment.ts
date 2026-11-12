import { request } from './client'
import type { SentimentResponse } from '../types/api'

export function getSentiment(): Promise<SentimentResponse> {
  return request<SentimentResponse>('/sentiment')
}

export function refreshSentiment(): Promise<SentimentResponse> {
  return request<SentimentResponse>('/sentiment/refresh', { method: 'POST' })
}
