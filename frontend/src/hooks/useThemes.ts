import { useQuery } from '@tanstack/react-query'
import { getThemeDetail, getThemes } from '../api/themes'
import type { ApiError } from '../api/client'
import type { ThemeDetailResponse, ThemesListResponse } from '../types/api'

export function useThemes() {
  return useQuery<ThemesListResponse, ApiError>({
    queryKey: ['themes'],
    queryFn: getThemes,
    // Static editorial content — changes only with a deploy.
    staleTime: Infinity,
  })
}

export function useThemeDetail(slug: string | null) {
  return useQuery<ThemeDetailResponse, ApiError>({
    queryKey: ['theme', slug],
    queryFn: () => getThemeDetail(slug!),
    // Fetched only while a theme is open — every detail hit costs live
    // Finnhub quote/profile calls (protects the free-tier quota).
    enabled: slug !== null,
    staleTime: 900_000,
  })
}
