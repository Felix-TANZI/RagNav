// frontend/src/api/stream.ts
// Lecture de /chat/stream (Server-Sent Events) avec fetch, EventSource ne permet ni POST ni en-tête Authorization
import { API, ApiError, authHeaders, refreshSession, toApiError } from './client'
import type { ChatOut } from './types'

export interface StreamHandlers {
  onStep: (step: string) => void
  onText: (text: string) => void
  onDone: (result: ChatOut) => void
  onError: (error: ApiError) => void
}

async function open(message: string, signal: AbortSignal, retry: boolean): Promise<Response> {
  const response = await fetch(`${API}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    credentials: 'same-origin',
    body: JSON.stringify({ message }),
    signal,
  })
  if (response.status === 401 && retry && (await refreshSession())) return open(message, signal, false)
  return response
}

function dispatch(block: string, handlers: StreamHandlers, requestId: string | null): void {
  const lines = Object.fromEntries(
    block.split('\n').map((line) => [line.slice(0, line.indexOf(':')), line.slice(line.indexOf(':') + 1).trim()]),
  )
  if (!lines.event || !lines.data) return
  const data = JSON.parse(lines.data)
  if (lines.event === 'statut') handlers.onStep(data.etape)
  else if (lines.event === 'texte') handlers.onText(data.texte)
  else if (lines.event === 'fin') handlers.onDone(data as ChatOut)
  else if (lines.event === 'erreur') handlers.onError(new ApiError(503, data.detail, data.request_id ?? requestId))
}

export async function streamChat(message: string, handlers: StreamHandlers, signal: AbortSignal): Promise<void> {
  let response: Response
  try {
    response = await open(message, signal, true)
  } catch (e) {
    if ((e as Error).name !== 'AbortError') handlers.onError(new ApiError(0, 'reseau', null))
    return
  }
  if (!response.ok || !response.body) {
    handlers.onError(await toApiError(response))
    return
  }
  const requestId = response.headers.get('X-Request-ID')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let end = buffer.indexOf('\n\n')
      while (end !== -1) {
        dispatch(buffer.slice(0, end), handlers, requestId)
        buffer = buffer.slice(end + 2)
        end = buffer.indexOf('\n\n')
      }
    }
  } catch (e) {
    if ((e as Error).name !== 'AbortError') handlers.onError(new ApiError(0, 'reseau', requestId))
  }
}
