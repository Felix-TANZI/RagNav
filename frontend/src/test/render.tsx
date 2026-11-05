// frontend/src/test/render.tsx
// Application rendue avec ses fournisseurs et une fausse API, routée par méthode et chemin
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import App from '../App'
import type { User } from '../api/types'
import { AuthProvider } from '../auth/AuthContext'
import { ToastProvider } from '../components/Toast'
import { I18nProvider } from '../i18n/I18n'

export type Handler = (init: RequestInit | undefined, url: URL) => Response | Promise<Response>

export const ALICE: User = { id: 'u1', name: 'Alice', email: 'alice@test.cm', role: 'client', is_active: true,
  created_at: '2026-11-01T10:00:00Z', last_login_at: null }
export const FELIX: User = { ...ALICE, id: 'u2', name: 'Felix', email: 'felix@test.cm', role: 'admin' }

export function json(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })
}

export function sse(events: [string, unknown][], headers: Record<string, string> = {}): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream({
    start(controller) {
      for (const [event, data] of events) {
        controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`))
      }
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream', ...headers } })
}

export function mockApi(user: User | null, routes: Record<string, Handler> = {}) {
  const calls: { key: string; init?: RequestInit }[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost')
    const key = `${init?.method ?? 'GET'} ${url.pathname.replace(/^\/api/, '')}`
    calls.push({ key, init })
    if (routes[key]) return routes[key](init, url)
    if (key === 'POST /auth/refresh') {
      return user ? json({ access_token: 'jeton', token_type: 'bearer', expires_in: 900, role: user.role }) : json({ detail: 'x' }, 401)
    }
    if (key === 'GET /auth/me') return user ? json(user) : json({ detail: 'x' }, 401)
    if (key === 'GET /health') return json({ status: 'ok', version: '0.1.0' })
    return json({ detail: `route non simulée ${key}` }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return calls
}

export function renderApp(path: string) {
  return render(
    <I18nProvider>
      <AuthProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[path]}>
            <App />
          </MemoryRouter>
        </ToastProvider>
      </AuthProvider>
    </I18nProvider>,
  )
}
