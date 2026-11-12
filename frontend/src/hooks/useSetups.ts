import { useQuery } from '@tanstack/react-query'
import { getSetups } from '../api/setups'
import type { ApiError } from '../api/client'
import type { SetupsResponse } from '../types/api'

export function useSetups() {
  return useQuery<SetupsResponse, ApiError>({
    queryKey: ['setups'],
    queryFn: getSetups,
    // The report changes once a day (17:00 ET job). The hourly refetch only
    // hits the backend's DB cache — no external API calls.
    staleTime: 3_300_000,
    refetchInterval: 3_600_000,
    // 404 just means no report has been generated yet — show the empty state
    // immediately instead of retrying.
    retry: (failureCount, error) => error.status !== 404 && failureCount < 3,
  })
}
