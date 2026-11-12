import { request } from './client'
import type { ThemeDetailResponse, ThemesListResponse } from '../types/api'

export function getThemes(): Promise<ThemesListResponse> {
  return request<ThemesListResponse>('/themes')
}

export function getThemeDetail(slug: string): Promise<ThemeDetailResponse> {
  return request<ThemeDetailResponse>(`/themes/${encodeURIComponent(slug)}`)
}
