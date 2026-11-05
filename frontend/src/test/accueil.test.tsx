// frontend/src/test/accueil.test.tsx
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ALICE, json, mockApi, renderApp, sse } from './render'

const SOURCE = { document_id: 'd1', document: 'architecture.pdf', title: 'Architecture générale', section: '3. Machines',
  page: 2, version: '1.2', score: 0.71 }

async function ask(question: string) {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText("Votre question à l'assistant"), question)
  await user.click(screen.getByRole('button', { name: 'Envoyer' }))
}

describe("accueil de l'espace client", () => {
  it("salue l'utilisateur et affiche l'état des services comme l'écran GANDAL", async () => {
    mockApi(ALICE)
    renderApp('/')
    expect(await screen.findByRole('heading', { level: 1, name: /Alice\.$/ })).toBeInTheDocument()
    expect(await screen.findByText('Tous les services GANDAL fonctionnent')).toBeInTheDocument()
    expect(screen.getByText("Bonjour Alice, comment puis-je vous aider aujourd'hui ?")).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Envoyer' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Trouver un port ou une adresse/ })).toBeInTheDocument()
  })

  it('affiche la réponse en continu puis la réponse finale avec citation et source', async () => {
    const calls = mockApi(ALICE, {
      'POST /chat/stream': () => sse([['statut', { etape: 'recherche' }], ['statut', { etape: 'redaction' }],
        ['texte', { texte: 'LiteLLM écoute ' }], ['texte', { texte: 'sur le port 4000 [3].' }],
        ['fin', { answer: 'LiteLLM écoute sur le port 4000 [1].', found: true, sources: [SOURCE] }]]),
    })
    renderApp('/')
    await ask('Sur quel port écoute LiteLLM ?')
    expect(await screen.findByRole('link', { name: 'Source 1, Architecture générale' })).toHaveAttribute('href',
      expect.stringMatching(/#source-\d+-1$/))
    expect(screen.getByText('Sur quel port écoute LiteLLM ?')).toBeInTheDocument()
    expect(screen.getByText('Architecture générale')).toBeInTheDocument()
    expect(screen.getByText('3. Machines · page 2 · version 1.2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ouvrir le document' })).toBeInTheDocument()
    const call = calls.find((c) => c.key === 'POST /chat/stream')
    expect(JSON.parse(String(call?.init?.body))).toEqual({ message: 'Sur quel port écoute LiteLLM ?' })
    const headers = (call?.init?.headers ?? {}) as Record<string, string>
    expect(headers.Authorization).toBe('Bearer jeton')
  })

  it("signale une information absente de la documentation", async () => {
    mockApi(ALICE, {
      'POST /chat/stream': () => sse([['statut', { etape: 'recherche' }], ['fin', {
        answer: 'Je ne trouve pas cette information dans la documentation GANDAL.', found: false, sources: [] }]]),
    })
    renderApp('/')
    await ask('Quelle est la recette du ndolé ?')
    expect(await screen.findByText('Information absente de la documentation')).toBeInTheDocument()
    expect(screen.queryByText('Sources')).not.toBeInTheDocument()
  })

  it('montre la panne avec sa référence et permet de réessayer', async () => {
    let attempts = 0
    mockApi(ALICE, {
      'POST /chat/stream': () => {
        attempts += 1
        return attempts === 1
          ? sse([['erreur', { detail: 'Assistant momentanément indisponible, référence abc123def', request_id: 'abc123def' }]])
          : sse([['fin', { answer: 'Grafana tourne sur le port 3000 [1].', found: true, sources: [SOURCE] }]])
      },
    })
    renderApp('/')
    await ask('Sur quel port tourne Grafana ?')
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent("Rien n'a été modifié")
    expect(alert).toHaveTextContent('abc123def')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Réessayer' }))
    await waitFor(() => expect(screen.getByRole('link', { name: /Source 1/ })).toBeInTheDocument())
    expect(attempts).toBe(2)
  })

  it('un raccourci prépare la question sans l’envoyer', async () => {
    const calls = mockApi(ALICE)
    renderApp('/')
    await userEvent.setup().click(await screen.findByRole('button', { name: /Retrouver une procédure/ }))
    expect(screen.getByLabelText("Votre question à l'assistant")).toHaveValue('Comment ')
    expect(calls.some((c) => c.key === 'POST /chat/stream')).toBe(false)
  })

  it('renvoie vers la connexion sans session', async () => {
    mockApi(null, { 'GET /health': () => json({ status: 'ok', version: '0.1.0' }) })
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Se connecter' })).toBeInTheDocument()
  })
})
