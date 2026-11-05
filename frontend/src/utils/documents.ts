// frontend/src/utils/documents.ts
// Un lien simple ne peut pas porter le jeton, le fichier est donc récupéré puis ouvert dans un nouvel onglet
import { API, authHeaders, refreshSession, toApiError } from '../api/client'

export async function fetchDocument(path: string): Promise<Blob> {
  const get = () => fetch(`${API}${path}`, { headers: authHeaders(), credentials: 'same-origin' })
  let response = await get()
  if (response.status === 401 && (await refreshSession())) response = await get()
  if (!response.ok) throw await toApiError(response)
  return response.blob()
}

export async function openDocument(path: string, page?: number | null): Promise<void> {
  const tab = window.open('', '_blank')
  try {
    const url = URL.createObjectURL(await fetchDocument(path))
    const target = page ? `${url}#page=${page}` : url
    if (tab) tab.location.href = target
    else window.location.href = target
    window.setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    tab?.close()
    throw error
  }
}

export async function downloadDocument(path: string, filename: string): Promise<void> {
  const url = URL.createObjectURL(await fetchDocument(path))
  const link = Object.assign(document.createElement('a'), { href: url, download: filename })
  link.click()
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
