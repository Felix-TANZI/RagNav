// frontend/src/App.tsx
import { useEffect, useState } from 'react'

type Service = { ok: boolean; url: string; error?: string; missing?: string[]; version?: string }
type Health = { status: string; version: string; services: Record<string, Service> }

const LABELS: Record<string, string> = { models: 'Serveur de modèles', qdrant: 'Index vectoriel Qdrant' }

export default function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setHealth)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <main>
      <h1>GANDAL-AI</h1>
      <p className="subtitle">RAG navigation, état de l'environnement</p>
      {error && <p className="ko">Service GANDAL-AI injoignable ({error})</p>}
      {!health && !error && <p>Vérification en cours</p>}
      {health && (
        <>
          <p className={health.status === 'ok' ? 'ok' : 'ko'}>
            Statut {health.status}, version {health.version}
          </p>
          <ul>
            {Object.entries(health.services).map(([name, s]) => (
              <li key={name} className={s.ok ? 'ok' : 'ko'}>
                <strong>{LABELS[name] ?? name}</strong> {s.ok ? 'disponible' : 'indisponible'}
                <span className="detail">
                  {s.url}
                  {s.version && `, version ${s.version}`}
                  {s.missing && s.missing.length > 0 && `, modèles manquants ${s.missing.join(', ')}`}
                  {s.error && `, ${s.error}`}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  )
}
