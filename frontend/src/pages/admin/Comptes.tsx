// frontend/src/pages/admin/Comptes.tsx
// Comptes admin et client, un admin ne peut pas se retirer ses propres droits, action grisée et expliquée
import { Shield, Trash2, UserCheck, UserPlus, UserRound, UserX, Users } from 'lucide-react'
import { useCallback, useEffect, useState, type SubmitEvent } from 'react'
import { api } from '../../api/client'
import type { Role, User } from '../../api/types'
import { useAuth } from '../../auth/context'
import { ActionMenu } from '../../components/ActionMenu'
import { ConfirmDialog, Dialog } from '../../components/Dialog'
import { EmptyState, ErrorBanner, Skeleton } from '../../components/Feedback'
import { StatusPill } from '../../components/StatusPill'
import { useToast } from '../../components/toastContext'
import { useI18n } from '../../i18n/context'
import { formatDateTime } from '../../utils/format'
import { Field, PASSWORD_MIN } from '../AuthPages'

function CreateAccount({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { t } = useI18n()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState<Role>('client')
  const [checked, setChecked] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const errors = {
    name: name.trim() ? null : t('inscription.erreurPrenom'),
    email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) ? null : t('inscription.erreurEmail'),
    password: password.length >= PASSWORD_MIN ? null : t('inscription.erreurMotDePasse', { min: PASSWORD_MIN }),
  }
  const submit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    setChecked(true)
    if (errors.name || errors.email || errors.password) return
    try {
      await api('/admin/users', { method: 'POST', json: { name: name.trim(), email: email.trim(), password, role } })
      onCreated()
    } catch (e) {
      setError(e)
    }
  }
  return (
    <Dialog title={t('comptes.creerTitre')} description={t('comptes.creerTexte')} onClose={onClose} footer={
      <>
        <button type="button" className="bouton bouton--secondaire" onClick={onClose}>{t('action.annuler')}</button>
        <button type="submit" form="formulaire-compte" className="bouton bouton--principal">{t('comptes.creer')}</button>
      </>
    }>
      <form id="formulaire-compte" className="formulaire" onSubmit={submit} noValidate>
        {error !== null && <ErrorBanner error={error} />}
        <Field label={t('champ.prenom')} value={name} onChange={setName} error={checked ? errors.name : null} />
        <Field label={t('champ.email')} value={email} onChange={setEmail} type="email"
          error={checked ? errors.email : null} />
        <Field label={t('comptes.motDePasseInitial')} value={password} onChange={setPassword} type="password"
          autoComplete="new-password" help={t('inscription.aideMotDePasse', { min: PASSWORD_MIN })}
          error={checked ? errors.password : null} />
        <fieldset className="choix">
          <legend className="texte-fort">{t('comptes.role')}</legend>
          {(['client', 'admin'] as Role[]).map((value) => (
            <label key={value} className="choix__option">
              <input type="radio" name="role" value={value} checked={role === value} onChange={() => setRole(value)} />
              <span>
                <span className="texte-fort">{t(value === 'admin' ? 'role.admin' : 'role.client')}</span>
                <span className="texte-legende">{t(value === 'admin' ? 'comptes.roleAdmin' : 'comptes.roleClient')}</span>
              </span>
            </label>
          ))}
        </fieldset>
      </form>
    </Dialog>
  )
}

export function AdminComptes() {
  const { t, lang } = useI18n()
  const { user: me } = useAuth()
  const toast = useToast()
  const [users, setUsers] = useState<User[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [creating, setCreating] = useState(false)
  const [deleting, setDeleting] = useState<User | null>(null)

  const load = useCallback(() => {
    api<User[]>('/admin/users').then((list) => {
      setUsers(list)
      setError(null)
    }).catch(setError)
  }, [])
  useEffect(load, [load])

  const update = async (target: User, patch: Partial<Pick<User, 'is_active' | 'role'>>, message: string) => {
    try {
      await api(`/admin/users/${target.id}`, { method: 'PATCH', json: patch })
      toast(message)
      load()
    } catch (e) {
      setError(e)
    }
  }

  const admins = users?.filter((u) => u.role === 'admin' && u.is_active).length ?? 0
  return (
    <main className="page">
      <div className="entete-page">
        <div>
          <h1 className="texte-h1">{t('comptes.titre')}</h1>
          <p className="texte-secondaire">
            {users ? t('comptes.resume', { n: users.length, admins }) : t('comptes.sousTitre')}
          </p>
        </div>
        <button type="button" className="bouton bouton--principal" onClick={() => setCreating(true)}>
          <UserPlus size={16} aria-hidden="true" />{t('comptes.creer')}
        </button>
      </div>
      {error !== null && <ErrorBanner error={error} onRetry={load} />}
      <div className="carte">
        {users === null && error === null && <div className="carte__corps"><Skeleton lines={5} /></div>}
        {users?.length === 0 && <EmptyState icon={Users} title={t('comptes.videTitre')} text={t('comptes.videTexte')} />}
        {users && users.length > 0 && (
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">{t('comptes.colCompte')}</th>
                <th scope="col">{t('comptes.role')}</th>
                <th scope="col">{t('docs.colStatut')}</th>
                <th scope="col">{t('comptes.colConnexion')}</th>
                <th scope="col"><span className="visuellement-cache">{t('action.actions')}</span></th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => {
                const self = u.id === me?.id
                const lastAdmin = u.role === 'admin' && u.is_active && admins <= 1
                const lock = self ? t('comptes.soiMeme') : lastAdmin ? t('comptes.dernierAdmin') : undefined
                return (
                  <tr key={u.id}>
                    <td>
                      <div className="cellule-document">
                        <span className="texte-fort">{u.name || '—'}{self && <span className="texte-legende"> · {t('comptes.vous')}</span>}</span>
                        <span className="texte-legende">{u.email}</span>
                      </div>
                    </td>
                    <td><span className="badge">{t(u.role === 'admin' ? 'role.admin' : 'role.client')}</span></td>
                    <td><StatusPill kind={u.is_active ? 'marche' : 'arrete'} label={t(u.is_active ? 'comptes.actif' : 'comptes.desactive')} /></td>
                    <td className="texte-secondaire">{u.last_login_at ? formatDateTime(u.last_login_at, lang) : t('comptes.jamais')}</td>
                    <td>
                      <ActionMenu label={u.email} actions={[
                        u.is_active
                          ? { label: t('comptes.desactiver'), icon: UserX, disabledReason: lock,
                              onSelect: () => update(u, { is_active: false }, t('comptes.desactiveOk')) }
                          : { label: t('comptes.activer'), icon: UserCheck,
                              onSelect: () => update(u, { is_active: true }, t('comptes.activeOk')) },
                        u.role === 'admin'
                          ? { label: t('comptes.passerClient'), icon: UserRound, disabledReason: lock,
                              onSelect: () => update(u, { role: 'client' }, t('comptes.roleOk')) }
                          : { label: t('comptes.passerAdmin'), icon: Shield,
                              onSelect: () => update(u, { role: 'admin' }, t('comptes.roleOk')) },
                        { label: t('action.supprimer'), icon: Trash2, destructive: true, disabledReason: lock,
                          onSelect: () => setDeleting(u) },
                      ]} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
      {creating && <CreateAccount onClose={() => setCreating(false)} onCreated={() => {
        setCreating(false)
        toast(t('comptes.creeOk'))
        load()
      }} />}
      {deleting && (
        <ConfirmDialog title={t('comptes.supprimerTitre')} phrase={deleting.email}
          message={t('comptes.supprimerTexte')} confirmLabel={t('action.supprimer')} onClose={() => setDeleting(null)}
          onConfirm={async () => {
            const target = deleting
            setDeleting(null)
            try {
              await api(`/admin/users/${target.id}`, { method: 'DELETE' })
              toast(t('comptes.supprimeOk'))
              load()
            } catch (e) {
              setError(e)
            }
          }} />
      )}
    </main>
  )
}
