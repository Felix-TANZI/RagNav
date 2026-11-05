// frontend/src/pages/admin/Documents.tsx
// Corpus de navigation (CU5), statuts actualisés pendant l'indexation, cause d'un échec et lien vers le journal
import { Download, FilePlus2, Library, Pencil, Plus, RefreshCw, Trash2, Upload } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api/client'
import type { AdminDocument, DocumentStatus, Formats } from '../../api/types'
import { ActionMenu } from '../../components/ActionMenu'
import { ConfirmDialog } from '../../components/Dialog'
import { EmptyState, ErrorBanner, Skeleton } from '../../components/Feedback'
import { StatusPill, type StatusKind } from '../../components/StatusPill'
import { useToast } from '../../components/toastContext'
import { useI18n } from '../../i18n/context'
import type { Key } from '../../i18n/fr'
import { downloadDocument } from '../../utils/documents'
import { formatDate, formatSize } from '../../utils/format'
import { DocumentForm, type FormMode } from './DocumentForm'

const DOCUMENT_STATUS: Record<DocumentStatus, { kind: StatusKind; label: Key }> = {
  pending: { kind: 'pause', label: 'statut.attente' },
  indexing: { kind: 'cours', label: 'statut.indexation' },
  indexed: { kind: 'marche', label: 'statut.indexe' },
  failed: { kind: 'erreur', label: 'statut.erreur' },
  deleting: { kind: 'cours', label: 'statut.suppression' },
}
const WORKING: DocumentStatus[] = ['pending', 'indexing', 'deleting']

export function AdminDocuments() {
  const { t, lang } = useI18n()
  const toast = useToast()
  const [docs, setDocs] = useState<AdminDocument[] | null>(null)
  const [formats, setFormats] = useState<Formats | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [form, setForm] = useState<FormMode | null>(null)
  const [deleting, setDeleting] = useState<AdminDocument | null>(null)

  const load = useCallback(() => {
    api<AdminDocument[]>('/admin/documents').then((list) => {
      setDocs(list)
      setError(null)
    }).catch(setError)
  }, [])

  useEffect(() => {
    load()
    api<Formats>('/admin/documents/formats').then(setFormats).catch(() => undefined)
  }, [load])

  const working = docs?.some((d) => WORKING.includes(d.status)) ?? false
  useEffect(() => {
    if (!working) return
    const timer = window.setInterval(load, 3000)
    return () => window.clearInterval(timer)
  }, [working, load])

  const act = async (run: () => Promise<unknown>, message: string) => {
    try {
      await run()
      toast(message)
      load()
    } catch (e) {
      setError(e)
    }
  }

  const failed = docs?.filter((d) => d.status === 'failed').length ?? 0
  const passages = docs?.reduce((sum, d) => sum + (d.status === 'indexed' ? d.chunks ?? 0 : 0), 0) ?? 0
  const state = failed ? t('docs.etatErreur', { n: failed }) : working ? t('docs.etatCours') : t('docs.etatOk')
  return (
    <main className="page">
      <div className="entete-page">
        <div>
          <h1 className="texte-h1">{t('docs.titre')}</h1>
          <p className="texte-secondaire">
            {docs ? `${t('docs.resume', { n: docs.length, passages })} · ${state}` : t('docs.sousTitre')}
          </p>
        </div>
        <button type="button" className="bouton bouton--principal" onClick={() => setForm({ kind: 'ajout' })}>
          <Plus size={16} aria-hidden="true" />{t('docs.ajouter')}
        </button>
      </div>
      {error !== null && <ErrorBanner error={error} onRetry={load} />}
      <div className="carte">
        {docs === null && error === null && <div className="carte__corps"><Skeleton lines={6} /></div>}
        {docs?.length === 0 && (
          <EmptyState icon={Library} title={t('docs.videTitre')} text={t('docs.videTexte')}
            action={<button type="button" className="bouton bouton--principal" onClick={() => setForm({ kind: 'ajout' })}>
              <FilePlus2 size={16} aria-hidden="true" />{t('docs.ajouter')}</button>} />
        )}
        {docs && docs.length > 0 && (
          <table className="tableau">
            <thead>
              <tr>
                <th scope="col">{t('docs.colDocument')}</th>
                <th scope="col">{t('docs.version')}</th>
                <th scope="col">{t('docs.colStatut')}</th>
                <th scope="col">{t('docs.colPassages')}</th>
                <th scope="col">{t('docs.colMaj')}</th>
                <th scope="col"><span className="visuellement-cache">{t('action.actions')}</span></th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => {
                const status = DOCUMENT_STATUS[doc.status]
                const busy = WORKING.includes(doc.status)
                const why = busy ? t('docs.occupe') : undefined
                return (
                  <tr key={doc.id}>
                    <td>
                      <div className="cellule-document">
                        <span className="texte-fort">{doc.title}</span>
                        <span className="mono texte-legende">{doc.filename} · {formatSize(doc.size, lang)}</span>
                        {doc.status === 'failed' && doc.error && (
                          <span className="cellule-document__erreur">
                            {doc.error} · <Link to={`/administration/journal?document=${doc.id}`}>{t('docs.voirJournal')}</Link>
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="mono">{doc.version}</td>
                    <td><StatusPill kind={status.kind} label={t(status.label)} /></td>
                    <td className="mono">
                      {doc.chunks ?? '—'}
                      {doc.ocr_pages ? <span className="texte-legende"> · {t('docs.ocr', { n: doc.ocr_pages })}</span> : null}
                    </td>
                    <td className="texte-secondaire">{formatDate(doc.updated_at, lang)}</td>
                    <td>
                      <ActionMenu label={doc.title} actions={[
                        { label: t('docs.remplacer'), icon: Upload, onSelect: () => setForm({ kind: 'remplacer', doc }),
                          disabledReason: why },
                        { label: t('docs.modifier'), icon: Pencil, onSelect: () => setForm({ kind: 'modifier', doc }),
                          disabledReason: why },
                        { label: t('docs.reindexer'), icon: RefreshCw, disabledReason: why, onSelect: () =>
                          act(() => api(`/admin/documents/${doc.id}/reindex`, { method: 'POST' }), t('docs.reindexation')) },
                        { label: t('docs.telecharger'), icon: Download, onSelect: () =>
                          downloadDocument(`/admin/documents/${doc.id}/file`, doc.filename).catch(setError) },
                        { label: t('action.supprimer'), icon: Trash2, destructive: true, onSelect: () => setDeleting(doc),
                          disabledReason: doc.status === 'deleting' ? why : undefined },
                      ]} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
      {form && (
        <DocumentForm mode={form} formats={formats} onClose={() => setForm(null)} onSaved={(_, message) => {
          setForm(null)
          toast(message)
          load()
        }} />
      )}
      {deleting && (
        <ConfirmDialog title={t('docs.supprimerTitre')} phrase={deleting.filename}
          message={t('docs.supprimerTexte', { titre: deleting.title })} confirmLabel={t('action.supprimer')}
          onClose={() => setDeleting(null)}
          onConfirm={async () => {
            setDeleting(null)
            await act(() => api(`/admin/documents/${deleting.id}`, { method: 'DELETE' }), t('docs.supprime'))
          }} />
      )}
    </main>
  )
}
