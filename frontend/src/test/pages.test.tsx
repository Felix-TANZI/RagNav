// frontend/src/test/pages.test.tsx
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { AdminDocument } from '../api/types'
import { ALICE, FELIX, json, mockApi, renderApp } from './render'

const DOC: AdminDocument = { id: 'd1', filename: 'architecture.pdf', title: 'Architecture générale', source: 'I1',
  version: '1.2', document_date: '2026-10-20', size: 52000, status: 'indexed', error: null, chunks: 10, ocr_pages: 0,
  created_at: '2026-11-01T10:00:00Z', updated_at: '2026-11-01T10:00:00Z', indexed_at: '2026-11-01T10:01:00Z' }

describe('connexion et inscription', () => {
  it('affiche le message du serveur si la connexion échoue', async () => {
    mockApi(null, { 'POST /auth/token': () => json({ detail: 'E-mail ou mot de passe incorrect, ou compte temporairement bloqué',
      request_id: 'ref42abcd' }, 401) })
    renderApp('/connexion')
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Adresse e-mail'), 'alice@test.cm')
    await user.type(screen.getByLabelText('Mot de passe'), 'mauvais')
    await user.click(screen.getByRole('button', { name: 'Se connecter' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou mot de passe incorrect')
  })

  it("vérifie les champs de l'inscription avant l'envoi", async () => {
    const calls = mockApi(null)
    renderApp('/inscription')
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Créer mon compte' }))
    expect(screen.getByText('Indiquez votre prénom.')).toBeInTheDocument()
    expect(screen.getByText(/adresse e-mail valide/)).toBeInTheDocument()
    expect(screen.getByText('Choisissez un mot de passe de 12 caractères au moins.')).toBeInTheDocument()
    expect(calls.some((c) => c.key === 'POST /auth/register')).toBe(false)
  })

  it("passe l'interface en anglais, déclare la langue et retient le choix", async () => {
    mockApi(ALICE)
    renderApp('/documentation')
    expect(await screen.findByRole('heading', { level: 1, name: 'Documentation' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('fr')
    await userEvent.setup().click(screen.getByRole('button', { name: 'EN' }))
    expect(await screen.findByRole('link', { name: 'Home' })).toBeInTheDocument()
    expect(document.documentElement.lang).toBe('en')
    expect(localStorage.getItem('gandal-langue')).toBe('en')
  })
})

describe('administration', () => {
  it("refuse l'administration à un client en expliquant qui peut donner l'accès", async () => {
    mockApi(ALICE)
    renderApp('/administration/documents')
    expect(await screen.findByText("Vous n'avez pas accès à l'administration")).toBeInTheDocument()
  })

  it('montre les statuts, la cause d’un échec et le lien vers le journal', async () => {
    mockApi(FELIX, {
      'GET /admin/documents': () => json([DOC, { ...DOC, id: 'd2', title: 'Procédure GPU', filename: 'gpu.tex',
        status: 'failed', error: 'Lecture du document, PDF protégé par un mot de passe', chunks: null }]),
      'GET /admin/documents/formats': () => json({ extensions: ['.pdf'], max_upload_mb: 50 }),
    })
    renderApp('/administration/documents')
    expect(await screen.findByText('Administration', { selector: '.etiquette-admin' })).toBeInTheDocument()
    expect(await screen.findByText('Indexé')).toBeInTheDocument()
    expect(screen.getByText('Erreur')).toBeInTheDocument()
    expect(screen.getByText(/2 document\(s\), 10 passages indexés · 1 document\(s\) à corriger/)).toBeInTheDocument()
    expect(screen.getByText(/PDF protégé par un mot de passe/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Voir le journal' })).toHaveAttribute('href', '/administration/journal?document=d2')
  })

  it('la suppression exige de recopier le nom du fichier', async () => {
    const calls = mockApi(FELIX, {
      'GET /admin/documents': () => json([DOC]),
      'GET /admin/documents/formats': () => json({ extensions: ['.pdf'], max_upload_mb: 50 }),
      'DELETE /admin/documents/d1': () => json(null, 202),
    })
    renderApp('/administration/documents')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Actions, Architecture générale' }))
    await user.click(screen.getByRole('menuitem', { name: 'Supprimer' }))
    const dialog = screen.getByRole('dialog', { name: 'Supprimer ce document ?' })
    const confirm = within(dialog).getByRole('button', { name: 'Supprimer' })
    expect(confirm).toBeDisabled()
    await user.type(within(dialog).getByLabelText(/Pour confirmer, recopiez/), 'architecture.pdf')
    expect(confirm).toBeEnabled()
    await user.click(confirm)
    await waitFor(() => expect(calls.some((c) => c.key === 'DELETE /admin/documents/d1')).toBe(true))
  })

  it('refuse un format de fichier non pris en charge avant tout envoi', async () => {
    const calls = mockApi(FELIX, {
      'GET /admin/documents': () => json([]),
      'GET /admin/documents/formats': () => json({ extensions: ['.pdf', '.md'], max_upload_mb: 50 }),
    })
    renderApp('/administration/documents')
    const user = userEvent.setup({ applyAccept: false })
    await user.click((await screen.findAllByRole('button', { name: 'Ajouter un document' }))[0])
    const dialog = screen.getByRole('dialog')
    await user.upload(within(dialog).getByLabelText('Fichier'), new File(['x'], 'installateur.exe'))
    await user.click(within(dialog).getByRole('button', { name: 'Envoyer le document' }))
    expect(within(dialog).getByText(/Le format \.exe n'est pas pris en charge/)).toBeInTheDocument()
    expect(calls.some((c) => c.key === 'POST /admin/documents')).toBe(false)
  })
})
