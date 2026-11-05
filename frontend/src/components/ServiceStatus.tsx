// frontend/src/components/ServiceStatus.tsx
// Ligne d'état des services en langage courant, comme sur l'accueil de GANDAL
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Health } from '../api/types'
import { useI18n } from '../i18n/context'

type State = 'ok' | 'degraded' | 'unknown' | 'loading'

export function ServiceStatus() {
  const { t } = useI18n()
  const [state, setState] = useState<State>('loading')

  useEffect(() => {
    let active = true
    const check = () =>
      api<Health>('/health', { retry: false })
        .then((h) => active && setState(h.status))
        .catch(() => active && setState('unknown'))
    check()
    const timer = window.setInterval(check, 60_000)
    return () => {
      active = false
      window.clearInterval(timer)
    }
  }, [])

  if (state === 'loading') return <p className="etat-services" aria-hidden="true">&nbsp;</p>
  const label = { ok: 'services.ok', degraded: 'services.degrade', unknown: 'services.inconnu' } as const
  return (
    <p className={`etat-services etat-services--${state}`} role="status">
      <span className="etat-services__pastille" aria-hidden="true" />
      {t(label[state])}
    </p>
  )
}
