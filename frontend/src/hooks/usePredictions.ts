import { useQuery } from '@tanstack/react-query'
import { getPredictionsSummary, getTickerPredictions } from '../api/predictions'
import type { ApiError } from '../api/client'
import type { PredictionsSummaryResponse, TickerPredictionsResponse } from '../types/api'

export function usePredictions() {
  return useQuery<PredictionsSummaryResponse, ApiError>({
    queryKey: ['predictions'],
    queryFn: getPredictionsSummary,
    // New rows appear once a day (17:10 ET job). DB-only backend — the hourly
    // refetch never triggers external API calls.
    staleTime: 3_300_000,
    refetchInterval: 3_600_000,
  })
}

export function useTickerPredictions(ticker: string | null) {
  return useQuery<TickerPredictionsResponse, ApiError>({
    queryKey: ['predictions', ticker],
    queryFn: () => getTickerPredictions(ticker!),
    enabled: ticker !== null,
    staleTime: 3_300_000,
    // 404 just means no predictions recorded for this ticker yet.
    retry: (failureCount, error) => error.status !== 404 && failureCount < 3,
  })
}
