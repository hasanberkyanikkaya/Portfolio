import { useQuery } from '@tanstack/react-query'
import { getHealth } from '../api/positions'
import type { ApiError } from '../api/client'
import type { HealthResponse } from '../types/api'

export function useHealth() {
  return useQuery<HealthResponse, ApiError>({
    queryKey: ['health'],
    queryFn: getHealth,
    refetchInterval: 60_000,
    retry: 0,
  })
}
