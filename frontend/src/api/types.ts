// frontend/src/api/types.ts
export type Role = 'admin' | 'client'

export interface User {
  id: string
  name: string
  email: string
  role: Role
  is_active: boolean
  created_at: string
  last_login_at: string | null
}

export interface TokenOut {
  access_token: string
  token_type: string
  expires_in: number
  role: Role
}

export interface Source {
  document_id: string
  document: string
  title: string
  section: string
  page: number | null
  version: string
  score: number
}

export interface ChatOut {
  answer: string
  found: boolean
  sources: Source[]
}

export interface LibraryDocument {
  id: string
  title: string
  filename: string
  source: string
  version: string
  document_date: string
  chunks: number | null
}

export type DocumentStatus = 'pending' | 'indexing' | 'indexed' | 'failed' | 'deleting'

export interface AdminDocument {
  id: string
  filename: string
  title: string
  source: string
  version: string
  document_date: string
  size: number
  status: DocumentStatus
  error: string | null
  chunks: number | null
  ocr_pages: number | null
  created_at: string
  updated_at: string
  indexed_at: string | null
}

export interface Formats {
  extensions: string[]
  max_upload_mb: number
}

export interface ServiceKey {
  id: string
  name: string
  prefix: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

export interface ServiceKeyCreated extends ServiceKey {
  key: string
}

export type EventLevel = 'info' | 'warning' | 'error'

export interface AppEvent {
  id: string
  created_at: string
  level: EventLevel
  category: string
  action: string
  message: string
  actor: string | null
  ip: string | null
  method: string | null
  path: string | null
  status_code: number | null
  request_id: string | null
  document_id: string | null
}

export interface AppEventDetail extends AppEvent {
  detail: string | null
}

export interface Health {
  status: 'ok' | 'degraded'
  version: string
}
