// frontend/src/pages/ClientPages.tsx
// Documentation consultable, compte de l'utilisateur et page introuvable
import { ExternalLink, FileText, Library } from 'lucide-react'
import { useCallback, useEffect, useState, type SubmitEvent } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { LibraryDocument, User } from '../api/types'
import { useAuth } from '../auth/context'
import { EmptyState, ErrorBanner, Skeleton } from '../components/Feedback'
import { useToast } from '../components/toastContext'
import { useI18n } from '../i18n/context'
import { openDocument } from '../utils/documents'
import { formatDate } from '../utils/format'
import { Field, PASSWORD_MIN } from './AuthPages'

export function Documentation() {
  const { t, lang } = useI18n()
  const [documents, setDocuments] = useState<LibraryDocument[] | null>(null)
  const [error, setError] = useState<unknown>(null)

  const fetchDocuments = useCallback(() => {
    api<LibraryDocument[]>('/documents').then(setDocuments).catch(setError)
  }, [])
  useEffect(fetchDocuments, [fetchDocuments])
  const retry = () => {
    setError(null)
    fetchDocuments()
  }

  return (
    <main className="page">
      <div className="entete-page">
        <div>
          <h1 className="texte-h1">{t('documentation.titre')}</h1>
          <p className="texte-secondaire">
            {documents ? t('documentation.resume', { n: documents.length }) : t('documentation.sousTitre')}
          </p>
        </div>
      </div>
      {error !== null && <ErrorBanner error={error} onRetry={retry} />}
      <div className="carte">
        {documents === null && error === null && <div className="carte__corps"><Skeleton lines={5} /></div>}
        {documents?.length === 0 && (
          <EmptyState icon={Library} title={t('documentation.videTitre')} text={t('documentation.videTexte')} />
        )}
        {documents && documents.length > 0 && (
          <ul className="liste-documents">
            {documents.map((doc) => (
              <li key={doc.id} className="liste-documents__item">
                <FileText size={20} aria-hidden="true" className="texte-secondaire" />
                <div className="liste-documents__texte">
                  <span className="texte-fort">{doc.title}</span>
                  <span className="texte-legende">
                    {doc.source} · {t('assistant.version', { version: doc.version })} · {formatDate(doc.document_date, lang)}
                  </span>
                </div>
                <button type="button" className="bouton bouton--secondaire bouton--petit"
                  onClick={() => openDocument(`/documents/${doc.id}/file`).catch(setError)}>
                  <ExternalLink size={16} aria-hidden="true" />{t('assistant.ouvrir')}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  )
}

export function Compte() {
  const { user, setUser } = useAuth()
  const { t } = useI18n()
  const toast = useToast()
  const [name, setName] = useState(user?.name ?? '')
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [profileError, setProfileError] = useState<unknown>(null)
  const [passwordError, setPasswordError] = useState<unknown>(null)
  const [checked, setChecked] = useState(false)
  const { logout } = useAuth()

  if (!user) return null
  const saveName = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    setProfileError(null)
    try {
      setUser(await api<User>('/auth/me', { method: 'PATCH', json: { name: name.trim() } }))
      toast(t('compte.prenomEnregistre'))
    } catch (e) {
      setProfileError(e)
    }
  }
  const nextError = next.length >= PASSWORD_MIN ? null : t('inscription.erreurMotDePasse', { min: PASSWORD_MIN })
  const savePassword = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    setChecked(true)
    if (nextError) return
    setPasswordError(null)
    try {
      await api('/auth/password', { method: 'POST', json: { current_password: current, new_password: next } })
      toast(t('compte.motDePasseChange'))
      await logout()
    } catch (e) {
      setPasswordError(e)
    }
  }

  return (
    <main className="page page--etroite">
      <div className="entete-page">
        <div>
          <h1 className="texte-h1">{t('compte.titre')}</h1>
          <p className="texte-secondaire">{user.email} · {t(user.role === 'admin' ? 'role.admin' : 'role.client')}</p>
        </div>
      </div>
      <form className="carte carte__corps formulaire" onSubmit={saveName}>
        <h2 className="texte-h3">{t('compte.profil')}</h2>
        {profileError !== null && <ErrorBanner error={profileError} />}
        <Field label={t('champ.prenom')} value={name} onChange={setName} autoComplete="given-name" />
        <div><button type="submit" className="bouton bouton--principal" disabled={!name.trim()}>{t('action.enregistrer')}</button></div>
      </form>
      <form className="carte carte__corps formulaire" onSubmit={savePassword}>
        <h2 className="texte-h3">{t('compte.motDePasse')}</h2>
        <p className="texte-secondaire">{t('compte.motDePasseAide')}</p>
        {passwordError !== null && <ErrorBanner error={passwordError} />}
        <Field label={t('compte.actuel')} value={current} onChange={setCurrent} type="password"
          autoComplete="current-password" />
        <Field label={t('compte.nouveau')} value={next} onChange={setNext} type="password" autoComplete="new-password"
          help={t('inscription.aideMotDePasse', { min: PASSWORD_MIN })} error={checked ? nextError : null} />
        <div><button type="submit" className="bouton bouton--secondaire" disabled={!current}>{t('compte.changer')}</button></div>
      </form>
    </main>
  )
}

export function Introuvable() {
  const { t } = useI18n()
  return (
    <main className="page">
      <div className="carte">
        <EmptyState icon={FileText} title={t('introuvable.titre')} text={t('introuvable.texte')}
          action={<Link className="bouton bouton--secondaire" to="/">{t('droits.retour')}</Link>} />
      </div>
    </main>
  )
}
