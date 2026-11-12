import { useQuery } from '@tanstack/react-query'
import { getRealized } from '../api/positions'
import type { ApiError } from '../api/client'
import type { RealizedTradesResponse } from '../types/api'

export function useRealized() {
  return useQuery<RealizedTradesResponse, ApiError>({
    queryKey: ['realized'],
    queryFn: getRealized,
    // Only changes when a position is closed — the mutation invalidates it.
    staleTime: Infinity,
  })
}
