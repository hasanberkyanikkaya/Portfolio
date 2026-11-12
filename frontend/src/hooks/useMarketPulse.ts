import { useQuery } from '@tanstack/react-query'
import { getMarketPulse } from '../api/marketPulse'
import type { ApiError } from '../api/client'
import type { MarketPulseResponse } from '../types/api'

export function useMarketPulse() {
  return useQuery<MarketPulseResponse, ApiError>({
    queryKey: ['market-pulse'],
    queryFn: getMarketPulse,
    // The report changes once a day (16:50 ET job). The hourly refetch only
    // hits the backend's DB cache — no external API calls — and picks up the
    // new report in a long-open tab (refetchOnWindowFocus is off globally).
    staleTime: 3_300_000,
    refetchInterval: 3_600_000,
    // 404 just means no report has been generated yet — show the empty state
    // immediately instead of retrying.
    retry: (failureCount, error) => error.status !== 404 && failureCount < 3,
  })
}
