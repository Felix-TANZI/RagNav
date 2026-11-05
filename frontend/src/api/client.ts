// frontend/src/api/client.ts
// Jeton d'accès gardé en mémoire uniquement, renouvelé une seule fois à la fois par le cookie HttpOnly
import type { TokenOut } from './types'

export const API = '/api'

export class ApiError extends Error {
  status: number
  requestId: string | null

  constructor(status: number, message: string, requestId: string | null) {
    super(message)
    this.status = status
    this.requestId = requestId
  }
}

let accessToken: string | null = null
let refreshing: Promise<boolean> | null = null

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export function authHeaders(): Record<string, string> {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {}
}

export function refreshSession(): Promise<boolean> {
  refreshing ??= fetch(`${API}/auth/refresh`, { method: 'POST', credentials: 'same-origin' })
    .then(async (r) => {
      if (!r.ok) {
        accessToken = null
        return false
      }
      accessToken = ((await r.json()) as TokenOut).access_token
      return true
    })
    .catch(() => false)
    .finally(() => {
      refreshing = null
    })
  return refreshing
}

function messageOf(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return `validation:${status}`
  return `http:${status}`
}

export async function toApiError(r: Response): Promise<ApiError> {
  const body = await r.json().catch(() => null)
  const requestId = (body as { request_id?: string } | null)?.request_id ?? r.headers.get('X-Request-ID')
  return new ApiError(r.status, messageOf(body, r.status), requestId)
}

interface Options {
  method?: string
  json?: unknown
  form?: FormData | URLSearchParams
  retry?: boolean
}

export async function api<T>(path: string, { method = 'GET', json, form, retry = true }: Options = {}): Promise<T> {
  const headers: Record<string, string> = { ...authHeaders() }
  if (json !== undefined) headers['Content-Type'] = 'application/json'
  let response: Response
  try {
    response = await fetch(`${API}${path}`, {
      method,
      headers,
      credentials: 'same-origin',
      body: json !== undefined ? JSON.stringify(json) : form,
    })
  } catch {
    throw new ApiError(0, 'reseau', null)
  }
  if (response.status === 401 && retry && !path.startsWith('/auth/token') && (await refreshSession())) {
    return api<T>(path, { method, json, form, retry: false })
  }
  if (!response.ok) throw await toApiError(response)
  if (response.status === 204) return undefined as T
  const text = await response.text()
  return (text ? JSON.parse(text) : undefined) as T
}
