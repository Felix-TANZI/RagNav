// frontend/src/components/Guards.tsx
// Accès aux pages selon la session et le rôle, une page sans droit explique qui peut accorder l'accès
import { Lock } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, Navigate, useLocation } from 'react-router'
import { useAuth } from '../auth/context'
import { useI18n } from '../i18n/context'
import { EmptyState, Skeleton } from './Feedback'

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'loading') {
    return <main className="page"><Skeleton lines={6} /></main>
  }
  if (status === 'anonymous') {
    return <Navigate to={`/connexion?suite=${encodeURIComponent(location.pathname)}`} replace />
  }
  return <>{children}</>
}

export function RequireAdmin({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  const { t } = useI18n()
  if (user?.role !== 'admin') {
    return (
      <main className="page">
        <div className="carte">
          <EmptyState icon={Lock} title={t('droits.titre')} text={t('droits.texte')}
            action={<Link className="bouton bouton--secondaire" to="/">{t('droits.retour')}</Link>} />
        </div>
      </main>
    )
  }
  return <>{children}</>
}
