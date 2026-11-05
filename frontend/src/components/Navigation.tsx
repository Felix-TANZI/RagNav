// frontend/src/components/Navigation.tsx
// Barre de l'espace client, barre bleu nuit de l'administration (charte page 27), langue et menu du compte
import { LogOut, Settings, Shield, UserRound } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router'
import { useAuth } from '../auth/context'
import { useI18n, type Lang } from '../i18n/context'
import type { Key } from '../i18n/fr'
import { Logo } from './Logo'

function initials(name: string, email: string): string {
  const source = name.trim() || email
  const parts = source.split(/[\s.@_-]+/).filter(Boolean)
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : source.slice(0, 2)).toUpperCase()
}

function LanguageSwitch({ inverse }: { inverse: boolean }) {
  const { lang, setLang, t } = useI18n()
  return (
    <div className={`langues${inverse ? ' langues--inverse' : ''}`} role="group" aria-label={t('nav.langue')}>
      {(['fr', 'en'] as Lang[]).map((code) => (
        <button key={code} type="button" className="langues__choix" aria-pressed={lang === code}
          onClick={() => setLang(code)}>
          {code.toUpperCase()}
        </button>
      ))}
    </div>
  )
}

function UserMenu({ admin }: { admin: boolean }) {
  const { user, logout } = useAuth()
  const { t } = useI18n()
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onClick = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClick)
    }
  }, [open])

  if (!user) return null
  const leave = async () => {
    await logout()
    navigate('/connexion')
  }
  return (
    <div className="menu" ref={root}>
      <button type="button" className="avatar" aria-haspopup="menu" aria-expanded={open}
        aria-label={t('nav.menu', { nom: user.name || user.email })} onClick={() => setOpen((v) => !v)}>
        {initials(user.name, user.email)}
      </button>
      {open && (
        <div className="menu__liste" role="menu">
          <div className="menu__entete">
            <span className="texte-fort">{user.name || user.email}</span>
            <span className="texte-legende">{user.email}</span>
          </div>
          <Link role="menuitem" className="menu__item" to="/compte" onClick={() => setOpen(false)}>
            <UserRound size={16} aria-hidden="true" />{t('nav.compte')}
          </Link>
          {user.role === 'admin' && (
            <Link role="menuitem" className="menu__item" to={admin ? '/' : '/administration'}
              onClick={() => setOpen(false)}>
              {admin ? <Settings size={16} aria-hidden="true" /> : <Shield size={16} aria-hidden="true" />}
              {t(admin ? 'nav.espaceClient' : 'nav.administration')}
            </Link>
          )}
          <button type="button" role="menuitem" className="menu__item" onClick={leave}>
            <LogOut size={16} aria-hidden="true" />{t('nav.deconnexion')}
          </button>
        </div>
      )}
    </div>
  )
}

interface BarProps {
  links: { to: string; label: Key; end?: boolean }[]
}

export function TopBar({ links }: BarProps) {
  const { t } = useI18n()
  return (
    <header className="barre">
      <div className="barre__contenu">
        <Link to="/" className="barre__logo"><Logo /></Link>
        <nav className="barre__liens" aria-label={t('nav.principale')}>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} end={link.end} className="barre__lien">{t(link.label)}</NavLink>
          ))}
        </nav>
        <div className="barre__droite">
          <LanguageSwitch inverse={false} />
          <UserMenu admin={false} />
        </div>
      </div>
    </header>
  )
}

export function AdminBar({ links }: BarProps) {
  const { t } = useI18n()
  return (
    <header className="barre barre--admin">
      <div className="barre__contenu">
        <Link to="/administration" className="barre__logo">
          <Logo inverse />
          <span className="etiquette-admin">{t('admin.etiquette')}</span>
        </Link>
        <nav className="barre__liens" aria-label={t('nav.administration')}>
          {links.map((link) => (
            <NavLink key={link.to} to={link.to} className="barre__lien">{t(link.label)}</NavLink>
          ))}
        </nav>
        <div className="barre__droite">
          <LanguageSwitch inverse />
          <UserMenu admin />
        </div>
      </div>
    </header>
  )
}
