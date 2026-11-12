import { useQuery } from '@tanstack/react-query'
import { getGlossary } from '../api/glossary'
import type { ApiError } from '../api/client'
import type { GlossaryResponse } from '../types/api'

export function useGlossary(enabled: boolean) {
  return useQuery<GlossaryResponse, ApiError>({
    queryKey: ['glossary'],
    queryFn: getGlossary,
    // Static backend content — fetch once (when the section is first opened)
    // and keep it for the whole session.
    staleTime: Infinity,
    gcTime: Infinity,
    enabled,
  })
}
