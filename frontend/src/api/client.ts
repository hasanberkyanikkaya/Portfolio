export class ApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

interface ValidationErrorItem {
  loc: (string | number)[]
  msg: string
}

// FastAPI returns `detail` as a string for HTTPExceptions (400/404/429/503)
// but as an array of {loc, msg} objects for 422 validation errors.
function parseDetail(body: unknown): string {
  if (typeof body === 'object' && body !== null && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return (detail as ValidationErrorItem[])
        .map((item) => {
          const field = item.loc?.slice(1).join('.') || 'input'
          return `${field}: ${item.msg}`
        })
        .join('; ')
    }
  }
  return 'Unexpected error from the server.'
}

const API_BASE: string = import.meta.env.VITE_API_BASE ?? ''

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: init?.body
        ? { 'Content-Type': 'application/json', ...init?.headers }
        : init?.headers,
    })
  } catch {
    throw new ApiError(0, 'Could not reach the backend. Is the API running?')
  }

  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      // non-JSON error body — fall through to generic message
    }
    throw new ApiError(res.status, parseDetail(body))
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}
