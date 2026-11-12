import { useQuery } from '@tanstack/react-query'
import { getTickerNews } from '../api/portfolio'
import type { ApiError } from '../api/client'
import type { TickerNewsResponse } from '../types/api'

/** Fetched lazily — the hook only mounts while the news dialog is open. */
export function useTickerNews(ticker: string) {
  return useQuery<TickerNewsResponse, ApiError>({
    queryKey: ['news', ticker],
    queryFn: () => getTickerNews(ticker),
    staleTime: 900_000,
  })
}
