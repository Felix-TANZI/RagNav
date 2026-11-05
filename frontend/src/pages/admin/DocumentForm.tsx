// frontend/src/pages/admin/DocumentForm.tsx
// Ajout, modification et remplacement d'un document, format et taille vérifiés avant l'envoi
import { Upload } from 'lucide-react'
import { useId, useState, type SubmitEvent } from 'react'
import { api } from '../../api/client'
import type { AdminDocument, Formats } from '../../api/types'
import { Dialog } from '../../components/Dialog'
import { ErrorBanner } from '../../components/Feedback'
import { useI18n } from '../../i18n/context'
import { formatSize } from '../../utils/format'
import { Field } from '../AuthPages'

export type FormMode = { kind: 'ajout' } | { kind: 'modifier'; doc: AdminDocument } | { kind: 'remplacer'; doc: AdminDocument }

interface Props {
  mode: FormMode
  formats: Formats | null
  onClose: () => void
  onSaved: (doc: AdminDocument, message: string) => void
}

function titleFrom(filename: string): string {
  const stem = filename.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim()
  return stem.charAt(0).toUpperCase() + stem.slice(1)
}

export function DocumentForm({ mode, formats, onClose, onSaved }: Props) {
  const { t, lang } = useI18n()
  const fileId = useId()
  const doc = mode.kind === 'ajout' ? null : mode.doc
  const [file, setFile] = useState<File | null>(null)
  const [title, setTitle] = useState(doc?.title ?? '')
  const [source, setSource] = useState(doc?.source ?? '')
  const [version, setVersion] = useState(mode.kind === 'remplacer' ? '' : doc?.version ?? '1.0')
  const [date, setDate] = useState(() => doc?.document_date ?? new Date().toISOString().slice(0, 10))
  const [checked, setChecked] = useState(false)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const needsFile = mode.kind !== 'modifier'

  const extension = file ? `.${file.name.split('.').pop()?.toLowerCase()}` : ''
  const maxBytes = (formats?.max_upload_mb ?? 50) * 1024 * 1024
  const fileError = !needsFile ? null : !file ? t('docs.erreurFichier')
    : formats && !formats.extensions.includes(extension) ? t('docs.erreurFormat', { ext: extension })
      : file.size > maxBytes ? t('docs.erreurTaille', { max: formats?.max_upload_mb ?? 50 }) : null
  const required = t('docs.erreurObligatoire')
  const errors = mode.kind === 'remplacer' ? { title: null, source: null, version: null }
    : { title: title.trim() ? null : required, source: source.trim() ? null : required,
        version: version.trim() ? null : required }

  const chooseFile = (chosen: File | null) => {
    setFile(chosen)
    if (chosen && mode.kind === 'ajout' && !title.trim()) setTitle(titleFrom(chosen.name))
  }

  const submit = async (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    setChecked(true)
    if (fileError || errors.title || errors.source || errors.version) return
    setBusy(true)
    setError(null)
    try {
      if (mode.kind === 'modifier') {
        const saved = await api<AdminDocument>(`/admin/documents/${mode.doc.id}`, { method: 'PATCH',
          json: { title: title.trim(), source: source.trim(), version: version.trim(), document_date: date } })
        onSaved(saved, t('docs.modifie'))
        return
      }
      const form = new FormData()
      form.append('file', file as File)
      if (mode.kind === 'ajout') {
        Object.entries({ title, source, version, document_date: date }).forEach(([k, v]) => form.append(k, v.trim()))
        onSaved(await api<AdminDocument>('/admin/documents', { method: 'POST', form }), t('docs.ajoute'))
      } else {
        if (version.trim()) form.append('version', version.trim())
        const saved = await api<AdminDocument>(`/admin/documents/${mode.doc.id}/file`, { method: 'PUT', form })
        onSaved(saved, t('docs.remplace'))
      }
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const titles = { ajout: 'docs.ajouterTitre', modifier: 'docs.modifierTitre', remplacer: 'docs.remplacerTitre' } as const
  return (
    <Dialog title={t(titles[mode.kind])} description={doc ? doc.title : t('docs.ajouterTexte')} onClose={onClose}
      footer={
        <>
          <button type="button" className="bouton bouton--secondaire" onClick={onClose}>{t('action.annuler')}</button>
          <button type="submit" form="formulaire-document" className="bouton bouton--principal" disabled={busy}>
            {t(mode.kind === 'modifier' ? 'action.enregistrer' : 'docs.envoyer')}
          </button>
        </>
      }>
      <form id="formulaire-document" className="formulaire" onSubmit={submit} noValidate>
        {error !== null && <ErrorBanner error={error} />}
        {needsFile && (
          <div className={`champ${checked && fileError ? ' champ--erreur' : ''}`}>
            <label htmlFor={fileId}>{t('docs.fichier')}</label>
            <label className="depot" htmlFor={fileId}
              onDragOver={(e) => e.preventDefault()}
              onDrop={(e) => {
                e.preventDefault()
                chooseFile(e.dataTransfer.files[0] ?? null)
              }}>
              <Upload size={20} aria-hidden="true" />
              <span>{file ? `${file.name} · ${formatSize(file.size, lang)}` : t('docs.deposer')}</span>
              <span className="texte-legende">{t('docs.formats', { max: formats?.max_upload_mb ?? 50 })}</span>
            </label>
            <input id={fileId} type="file" className="visuellement-cache" accept={formats?.extensions.join(',')}
              onChange={(e) => chooseFile(e.target.files?.[0] ?? null)} />
            {checked && fileError && <span className="champ__erreur">{fileError}</span>}
          </div>
        )}
        {mode.kind !== 'remplacer' && (
          <>
            <Field label={t('docs.titreChamp')} value={title} onChange={setTitle} error={checked ? errors.title : null} />
            <Field label={t('docs.source')} value={source} onChange={setSource} help={t('docs.sourceAide')}
              error={checked ? errors.source : null} />
          </>
        )}
        <div className="formulaire__ligne">
          <Field label={t('docs.version')} value={version} onChange={setVersion}
            help={mode.kind === 'remplacer' ? t('docs.versionAide', { version: doc?.version ?? '' }) : undefined}
            error={checked ? errors.version : null} />
          {mode.kind !== 'remplacer' && <Field label={t('docs.date')} value={date} onChange={setDate} type="date" />}
        </div>
      </form>
    </Dialog>
  )
}
