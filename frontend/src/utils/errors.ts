// frontend/src/utils/errors.ts
// Message d'erreur dans la langue de l'interface, le message précis du serveur est gardé en français
import { ApiError } from '../api/client'
import { useI18n } from '../i18n/context'
import type { Key } from '../i18n/fr'

const BY_STATUS: Record<number, Key> = {
  0: 'erreur.reseau',
  401: 'erreur.401',
  403: 'erreur.403',
  404: 'erreur.404',
  409: 'erreur.409',
  413: 'erreur.413',
  415: 'erreur.415',
  422: 'erreur.422',
  429: 'erreur.429',
  503: 'erreur.503',
}

export function useErrorMessage(): (error: unknown) => string {
  const { t, lang } = useI18n()
  return (error: unknown) => {
    if (!(error instanceof ApiError)) return t('erreur.interne')
    const fromServer = !/^(reseau|validation:|http:)/.test(error.message)
    if (fromServer && lang === 'fr') return error.message
    return t(BY_STATUS[error.status] ?? 'erreur.interne')
  }
}
