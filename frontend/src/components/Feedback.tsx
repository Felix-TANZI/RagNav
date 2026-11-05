// frontend/src/components/Feedback.tsx
// États prévus pour chaque écran (charte page 32), chargement, liste vide, erreur avec sa référence
import { AlertTriangle, CircleX, Lock, RotateCcw, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { ApiError } from '../api/client'
import { useI18n } from '../i18n/context'
import { useErrorMessage } from '../utils/errors'

export function Skeleton({ lines = 4, height = 20 }: { lines?: number; height?: number }) {
  const { t } = useI18n()
  return (
    <div className="squelettes" role="status" aria-label={t('etat.chargement')}>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="squelette" style={{ height, width: `${92 - (i % 3) * 14}%` }} />
      ))}
    </div>
  )
}

interface EmptyProps {
  icon: LucideIcon
  title: string
  text: string
  action?: ReactNode
}

export function EmptyState({ icon: Icon, title, text, action }: EmptyProps) {
  return (
    <div className="vide">
      <span className="vide__icone"><Icon size={20} aria-hidden="true" /></span>
      <p className="texte-h3">{title}</p>
      <p className="texte-secondaire">{text}</p>
      {action}
    </div>
  )
}

interface BannerProps {
  error: unknown
  onRetry?: () => void
}

export function ErrorBanner({ error, onRetry }: BannerProps) {
  const { t } = useI18n()
  const message = useErrorMessage()
  const status = error instanceof ApiError ? error.status : 500
  const reference = error instanceof ApiError ? error.requestId : null
  const unavailable = status === 0 || status >= 500
  const conflict = status === 409
  const Icon = conflict ? AlertTriangle : status === 403 ? Lock : CircleX
  return (
    <div className={`bandeau ${conflict ? 'bandeau--attention' : 'bandeau--erreur'}`} role="alert">
      <Icon size={20} aria-hidden="true" />
      <div className="bandeau__texte">
        <span className="texte-fort">{unavailable ? t('erreur.rienModifie') : message(error)}</span>
        {unavailable && <span className="bandeau__detail">{message(error)}</span>}
        {reference && <span className="bandeau__detail">{t('erreur.reference')} <span className="mono">{reference}</span></span>}
      </div>
      {onRetry && (
        <button type="button" className="bouton bouton--secondaire bouton--petit" onClick={onRetry}>
          <RotateCcw size={16} aria-hidden="true" />
          {t('action.reessayer')}
        </button>
      )}
    </div>
  )
}
