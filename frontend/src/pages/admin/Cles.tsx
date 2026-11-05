// frontend/src/pages/admin/Cles.tsx
// Clés des applications appelantes, la clé complète n'est affichée qu'une seule fois, à sa création
import { Check, Copy, KeyRound, Plus, Trash2 } from 'lucide-react'
import { useCallback, useEffect, useState, type SubmitEvent } from 'react'
import { api } from '../../api/client'
import type { ServiceKey, ServiceKeyCreated } from '../../api/types'
import { ActionMenu } from '../../components/ActionMenu'
import { ConfirmDialog, Dialog } from '../../components/Dialog'
import { EmptyState, ErrorBanner, Skeleton } from '../../components/Feedback'
import { StatusPill } from '../../components/StatusPill'
import { useToast } from '../../components/toastContext'
import { useI18n } from '../../i18n/context'
import { formatDateTime } from '../../utils/format'
import { Field } from '../AuthPages'

function CreateKey({ onClose, onCreated }: { onClose: () => void; onCreated: () => void }) {
  const { t } = useI18n()
  const [name, setName] = useState('')
  const [created, setCreated] = useState<ServiceKeyCreated | null>(null)
  const [copied, setCopied] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const submit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!name.trim()) return
    try {
      setCreated(await api<ServiceKeyCreated>('/admin/service-keys', { method: 'POST', json: { name: name.trim() } }))
      onCreated()
    } catch (e) {
      setError(e)
    }
  }
  const copy = async () => {
    await navigator.clipboard.writeText(created?.key ?? '')
    setCopied(true)
  }
  if (created) {
    return (
      <Dialog title={t('cles.creeeTitre')} onClose={onClose} footer={
        <button type="button" className="bouton bouton--principal" onClick={onClose}>{t('cles.copieeFermer')}</button>
      }>
        <div className="bandeau bandeau--attention" role="note">
          <KeyRound size={20} aria-hidden="true" />
          <span>{t('cles.uneFois')}</span>
        </div>
        <div className="cle">
          <code className="mono cle__valeur">{created.key}</code>
          <button type="button" className="bouton bouton--secondaire bouton--petit" onClick={copy}>
            {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
            {t(copied ? 'cles.copiee' : 'cles.copier')}
          </button>
        </div>
        <p className="texte-secondaire">{t('cles.usage')} <code className="mono">X-API-Key</code></p>
      </Dialog>
    )
  }
  return (
    <Dialog title={t('cles.creerTitre')} description={t('cles.creerTexte')} onClose={onClose} footer={
      <>
        <button type="button" className="bouton bouton--secondaire" onClick={onClose}>{t('action.annuler')}</button>
        <button type="submit" form="formulaire-cle" className="bouton bouton--principal" disabled={!name.trim()}>
          {t('cles.creer')}
        </button>
      </>
    }>
      <form id="formulaire-cle" className="formulaire" onSubmit={submit}>
        {error !== null && <ErrorBanner error={error} />}
        <Field label={t('cles.nom')} value={name} onChange={setName} help={t('cles.nomAide')} />
      </form>
    </Dialog>
  )
}

export function AdminCles() {
  const { t, lang } = useI18n()
  const toast = useToast()
  const [keys, setKeys] = useState<ServiceKey[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [creating, setCreating] = useState(false)
  const [revoking, setRevoking] = useState<ServiceKey | null>(null)

  const load = useCallback(() => {
    api<ServiceKey[]>('/admin/service-keys').then((list) => {
      setKeys(list)
      setError(null)
    }).catch(setError)
  }, [])
  useEffect(load, [load])

  const active = keys?.filter((k) => !k.revoked_at).length ?? 0
  return (
    <main className="page">
      <div className="entete-page">
        <div>
          <h1 className="texte-h1">{t('cles.titre')}</h1>
          <p className="texte-secondaire">{keys ? t('cles.resume', { n: active }) : t('cles.sousTitre')}</p>
        </div>
        <button type="button" className="bouton bouton--principal" onClick={() => setCreating(true)}>
          <Plus size={16} aria-hidden="true" />{t('cles.creer')}
        </button>
      </div>
      {error !== null && <ErrorBanner error={error} onRetry={load} />}
      <div className="carte">
        {keys === null && error === null && <div className="carte__corps"><Skeleton lines={4} /></div>}
        {keys?.length === 0 && (
          <EmptyState icon={KeyRound} title={t('cles.videTitre')} text={t('cles.videTexte')} />
        )}
        {keys && keys.length > 0 && (
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">{t('cles.application')}</th>
                <th scope="col">{t('cles.debut')}</th>
                <th scope="col">{t('docs.colStatut')}</th>
                <th scope="col">{t('cles.utilisation')}</th>
                <th scope="col"><span className="visuellement-cache">{t('action.actions')}</span></th>
              </tr>
            </thead>
            <tbody>
              {keys.map((key) => (
                <tr key={key.id}>
                  <td className="texte-fort">{key.name}</td>
                  <td className="mono">{key.prefix}…</td>
                  <td><StatusPill kind={key.revoked_at ? 'arrete' : 'marche'} label={t(key.revoked_at ? 'cles.revoquee' : 'cles.active')} /></td>
                  <td className="texte-secondaire">{key.last_used_at ? formatDateTime(key.last_used_at, lang) : t('cles.jamais')}</td>
                  <td>
                    <ActionMenu label={key.name} actions={[{ label: t('cles.revoquer'), icon: Trash2, destructive: true,
                      disabledReason: key.revoked_at ? t('cles.dejaRevoquee') : undefined, onSelect: () => setRevoking(key) }]} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {creating && <CreateKey onClose={() => setCreating(false)} onCreated={load} />}
      {revoking && (
        <ConfirmDialog title={t('cles.revoquerTitre')} phrase={revoking.name} message={t('cles.revoquerTexte')}
          confirmLabel={t('cles.revoquer')} onClose={() => setRevoking(null)} onConfirm={async () => {
            const target = revoking
            setRevoking(null)
            try {
              await api(`/admin/service-keys/${target.id}`, { method: 'DELETE' })
              toast(t('cles.revoqueeOk'))
              load()
            } catch (e) {
              setError(e)
            }
          }} />
      )}
    </main>
  )
}
