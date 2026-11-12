import { ApiError } from '../api/client'

// Maps ApiError statuses to user-friendly messages. 400/404 show the backend
// detail verbatim (e.g. "'ZZZZ' was not found as a NASDAQ-listed symbol.").
function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 429:
        return 'Finnhub rate limit reached — wait a minute and try again.'
      case 503:
        return 'Price service (Finnhub) is unreachable right now.'
      default:
        return error.detail
    }
  }
  return 'Something went wrong.'
}

export function ErrorBanner({ error }: { error: unknown }) {
  return (
    <div className="rounded-lg border border-loss/30 bg-loss/10 px-4 py-2.5 text-sm text-loss">
      {errorMessage(error)}
    </div>
  )
}
