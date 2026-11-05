// frontend/src/pages/AuthPages.tsx
// Connexion et inscription des clients, l'aide sous les champs dit quoi faire (gestion des erreurs)
import { Eye, EyeOff } from 'lucide-react'
import { useId, useState, type SubmitEvent, type ReactNode } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router'
import { useAuth } from '../auth/context'
import { ErrorBanner } from '../components/Feedback'
import { Logo } from '../components/Logo'
import { useI18n } from '../i18n/context'

export const PASSWORD_MIN = 12
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function AuthLayout({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  const { status } = useAuth()
  const [params] = useSearchParams()
  if (status === 'authenticated') return <Navigate to={params.get('suite') || '/'} replace />
  return (
    <main className="page-auth">
      <div className="carte auth">
        <Logo />
        <div>
          <h1 className="texte-h1">{title}</h1>
          <p className="texte-secondaire">{subtitle}</p>
        </div>
        {children}
      </div>
    </main>
  )
}

interface FieldProps {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  help?: string
  error?: string | null
  autoComplete?: string
}

export function Field({ label, value, onChange, type = 'text', help, error, autoComplete }: FieldProps) {
  const id = useId()
  const { t } = useI18n()
  const [visible, setVisible] = useState(false)
  const secret = type === 'password'
  const describedBy = error ? `${id}-erreur` : help ? `${id}-aide` : undefined
  return (
    <div className={`champ${error ? ' champ--erreur' : ''}`}>
      <label htmlFor={id}>{label}</label>
      <div className={secret ? 'champ__secret' : undefined}>
        <input id={id} type={secret && visible ? 'text' : type} value={value} autoComplete={autoComplete}
          onChange={(e) => onChange(e.target.value)} aria-invalid={Boolean(error)} aria-describedby={describedBy} />
        {secret && (
          <button type="button" className="bouton bouton--discret bouton--petit" onClick={() => setVisible((v) => !v)}
            aria-label={t(visible ? 'champ.masquer' : 'champ.afficher')} title={t(visible ? 'champ.masquer' : 'champ.afficher')}>
            {visible ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
          </button>
        )}
      </div>
      {error ? <span id={`${id}-erreur`} className="champ__erreur">{error}</span>
        : help && <span id={`${id}-aide`} className="champ__aide">{help}</span>}
    </div>
  )
}

export function Connexion() {
  const { login } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email.trim(), password)
      navigate(params.get('suite') || '/', { replace: true })
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title={t('connexion.titre')} subtitle={t('connexion.sousTitre')}>
      <form className="formulaire" onSubmit={submit} noValidate>
        {error !== null && <ErrorBanner error={error} />}
        <Field label={t('champ.email')} value={email} onChange={setEmail} type="email" autoComplete="email" />
        <Field label={t('champ.motDePasse')} value={password} onChange={setPassword} type="password"
          autoComplete="current-password" />
        <button type="submit" className="bouton bouton--principal" disabled={busy || !email || !password}>
          {t('connexion.action')}
        </button>
      </form>
      <p className="texte-secondaire">{t('connexion.pasDeCompte')} <Link to="/inscription">{t('connexion.creer')}</Link></p>
    </AuthLayout>
  )
}

export function Inscription() {
  const { register } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [checked, setChecked] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)

  const errors = {
    name: name.trim() ? null : t('inscription.erreurPrenom'),
    email: EMAIL.test(email.trim()) ? null : t('inscription.erreurEmail'),
    password: password.length >= PASSWORD_MIN ? null : t('inscription.erreurMotDePasse', { min: PASSWORD_MIN }),
  }

  const submit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    setChecked(true)
    if (errors.name || errors.email || errors.password) return
    setBusy(true)
    setError(null)
    try {
      await register(name.trim(), email.trim(), password)
      navigate('/', { replace: true })
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout title={t('inscription.titre')} subtitle={t('inscription.sousTitre')}>
      <form className="formulaire" onSubmit={submit} noValidate>
        {error !== null && <ErrorBanner error={error} />}
        <Field label={t('champ.prenom')} value={name} onChange={setName} autoComplete="given-name"
          help={t('inscription.aidePrenom')} error={checked ? errors.name : null} />
        <Field label={t('champ.email')} value={email} onChange={setEmail} type="email" autoComplete="email"
          error={checked ? errors.email : null} />
        <Field label={t('champ.motDePasse')} value={password} onChange={setPassword} type="password"
          autoComplete="new-password" help={t('inscription.aideMotDePasse', { min: PASSWORD_MIN })}
          error={checked ? errors.password : null} />
        <button type="submit" className="bouton bouton--principal" disabled={busy}>{t('inscription.action')}</button>
      </form>
      <p className="texte-secondaire">{t('inscription.dejaCompte')} <Link to="/connexion">{t('inscription.seConnecter')}</Link></p>
    </AuthLayout>
  )
}
