import { useQuery } from '@tanstack/react-query'
import { getPortfolioTechnical } from '../api/portfolio'
import type { ApiError } from '../api/client'
import type { PortfolioTechnicalResponse } from '../types/api'

export function useTechnical() {
  return useQuery<PortfolioTechnicalResponse, ApiError>({
    queryKey: ['technical'],
    queryFn: getPortfolioTechnical,
    // Daily closes change once a day and the backend memoizes them per
    // (ticker, NY date) — a long staleTime protects Yahoo's unofficial API.
    // The positions table's 15-min poll stays the "live" signal.
    staleTime: 3_300_000,
  })
}
