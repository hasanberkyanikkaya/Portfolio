import { useQuery } from '@tanstack/react-query'
import { getPositions } from '../api/positions'
import type { ApiError } from '../api/client'
import type { PortfolioResponse } from '../types/api'

export function usePositions() {
  return useQuery<PortfolioResponse, ApiError>({
    queryKey: ['positions'],
    queryFn: getPositions,
    // Requirement: refresh prices every 15 minutes.
    refetchInterval: 900_000,
  })
}
