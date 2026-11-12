import { useQuery } from '@tanstack/react-query'
import { getRiskProfile } from '../api/riskProfile'
import type { ApiError } from '../api/client'
import type { RiskProfileOut } from '../types/api'

export function useRiskProfile() {
  return useQuery<RiskProfileOut, ApiError>({
    queryKey: ['risk-profile'],
    queryFn: getRiskProfile,
    // Only changes when the user re-submits the questionnaire (mutation
    // invalidates the key).
    staleTime: Infinity,
    // 404 just means the questionnaire has never been filled in.
    retry: (failureCount, error) => error.status !== 404 && failureCount < 3,
  })
}
