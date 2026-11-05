// frontend/src/pages/admin/Journal.tsx
// Journal des événements, filtres, recherche par référence et fiche avec la trace technique
import { ScrollText, Search, X } from 'lucide-react'
import { useCallback, useEffect, useState, type SubmitEvent } from 'react'
import { useSearchParams } from 'react-router'
import { api } from '../../api/client'
import type { AppEvent, AppEventDetail, EventLevel } from '../../api/types'
import { EmptyState, ErrorBanner, Skeleton } from '../../components/Feedback'
import { StatusPill, type StatusKind } from '../../components/StatusPill'
import { useI18n } from '../../i18n/context'
import type { Key } from '../../i18n/fr'
import { formatDateTime } from '../../utils/format'

const PAGE = 50
const LEVELS: Record<EventLevel, { kind: StatusKind; label: Key }> = {
  info: { kind: 'arrete', label: 'journal.info' },
  warning: { kind: 'pause', label: 'journal.avertissement' },
  error: { kind: 'erreur', label: 'journal.erreur' },
}
const CATEGORIES = ['indexation', 'chat', 'authentification', 'documents', 'comptes', 'cles', 'api', 'systeme']

function Detail({ eventId, onClose }: { eventId: string; onClose: () => void }) {
  const { t, lang } = useI18n()
  const [event, setEvent] = useState<AppEventDetail | null>(null)
  const [error, setError] = useState<unknown>(null)
  useEffect(() => {
    api<AppEventDetail>(`/admin/events/${eventId}`).then(setEvent).catch(setError)
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [eventId, onClose])
  const rows: [Key, string | number | null | undefined][] = event ? [
    ['journal.date', formatDateTime(event.created_at, lang)], ['journal.categorie', event.category],
    ['journal.action', event.action], ['journal.auteur', event.actor], ['journal.ip', event.ip],
    ['journal.route', event.path ? `${event.method} ${event.path}` : null], ['journal.code', event.status_code],
    ['journal.reference', event.request_id], ['journal.document', event.document_id],
  ] : []
  return (
    <aside className="panneau" aria-labelledby="titre-evenement">
      <div className="fenetre__entete">
        <h2 id="titre-evenement" className="texte-h2">{t('journal.fiche')}</h2>
        <button type="button" className="bouton bouton--discret bouton--petit" onClick={onClose}
          aria-label={t('action.fermer')} title={t('action.fermer')}><X size={16} aria-hidden="true" /></button>
      </div>
      {error !== null && <ErrorBanner error={error} />}
      {!event && error === null && <Skeleton lines={6} />}
      {event && (
        <>
          <StatusPill kind={LEVELS[event.level].kind} label={t(LEVELS[event.level].label)} />
          <p>{event.message}</p>
          <dl className="fiche">
            {rows.filter(([, value]) => value !== null && value !== undefined).map(([label, value]) => (
              <div key={label} className="fiche__ligne">
                <dt className="texte-legende">{t(label)}</dt>
                <dd className={['journal.reference', 'journal.document', 'journal.ip', 'journal.route'].includes(label)
                  ? 'mono' : undefined}>{value}</dd>
              </div>
            ))}
          </dl>
          {event.detail && (
            <div>
              <p className="texte-legende">{t('journal.detail')}</p>
              <pre className="trace mono">{event.detail}</pre>
            </div>
          )}
        </>
      )}
    </aside>
  )
}

export function AdminJournal() {
  const { t, lang } = useI18n()
  const [params, setParams] = useSearchParams()
  const [events, setEvents] = useState<AppEvent[] | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [more, setMore] = useState(false)
  const [selected, setSelected] = useState<string | null>(null)
  const closeDetail = useCallback(() => setSelected(null), [])
  const [reference, setReference] = useState(params.get('reference') ?? '')
  const level = params.get('gravite') ?? ''
  const category = params.get('categorie') ?? ''
  const documentId = params.get('document') ?? ''
  const requestId = params.get('reference') ?? ''

  const query = useCallback((offset: number) => {
    const search = new URLSearchParams({ limit: String(PAGE), offset: String(offset) })
    if (level) search.set('level', level)
    if (category) search.set('category', category)
    if (documentId) search.set('document_id', documentId)
    if (requestId) search.set('request_id', requestId)
    return api<AppEvent[]>(`/admin/events?${search}`)
  }, [level, category, documentId, requestId])

  const fetchFirst = useCallback(() => {
    query(0).then((list) => {
      setEvents(list)
      setMore(list.length === PAGE)
    }).catch(setError)
  }, [query])
  useEffect(fetchFirst, [fetchFirst])
  const load = () => {
    setEvents(null)
    setError(null)
    fetchFirst()
  }

  const loadMore = () => query(events?.length ?? 0).then((list) => {
    setEvents((current) => [...(current ?? []), ...list])
    setMore(list.length === PAGE)
  }).catch(setError)

  const setFilter = (name: string, value: string) => {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value)
    else next.delete(name)
    setEvents(null)
    setError(null)
    setParams(next)
  }
  const searchReference = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    setFilter('reference', reference.trim())
  }

  return (
    <main className="page page--avec-panneau">
      <div className="page__principal">
        <div className="entete-page">
          <div>
            <h1 className="texte-h1">{t('journal.titre')}</h1>
            <p className="texte-secondaire">{t('journal.sousTitre')}</p>
          </div>
        </div>
        <div className="filtres">
          <div className="champ">
            <label htmlFor="filtre-gravite">{t('journal.gravite')}</label>
            <select id="filtre-gravite" value={level} onChange={(e) => setFilter('gravite', e.target.value)}>
              <option value="">{t('journal.toutes')}</option>
              {(Object.keys(LEVELS) as EventLevel[]).map((l) => <option key={l} value={l}>{t(LEVELS[l].label)}</option>)}
            </select>
          </div>
          <div className="champ">
            <label htmlFor="filtre-categorie">{t('journal.categorie')}</label>
            <select id="filtre-categorie" value={category} onChange={(e) => setFilter('categorie', e.target.value)}>
              <option value="">{t('journal.toutes')}</option>
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <form className="champ filtres__reference" onSubmit={searchReference}>
            <label htmlFor="filtre-reference">{t('journal.reference')}</label>
            <div className="filtres__recherche">
              <input id="filtre-reference" className="mono" value={reference} onChange={(e) => setReference(e.target.value)}
                placeholder={t('journal.referenceAide')} />
              <button type="submit" className="bouton bouton--secondaire"><Search size={16} aria-hidden="true" />{t('journal.chercher')}</button>
            </div>
          </form>
          {documentId && (
            <button type="button" className="bouton bouton--discret bouton--petit filtres__document"
              onClick={() => setFilter('document', '')}>
              <X size={16} aria-hidden="true" />{t('journal.filtreDocument')}
            </button>
          )}
        </div>
        {error !== null && <ErrorBanner error={error} onRetry={load} />}
        <div className="carte">
          {events === null && error === null && <div className="carte__corps"><Skeleton lines={8} /></div>}
          {events?.length === 0 && <EmptyState icon={ScrollText} title={t('journal.videTitre')} text={t('journal.videTexte')} />}
          {events && events.length > 0 && (
            <table className="tableau tableau--cliquable">
              <thead>
                <tr>
                  <th scope="col">{t('journal.date')}</th>
                  <th scope="col">{t('journal.gravite')}</th>
                  <th scope="col">{t('journal.categorie')}</th>
                  <th scope="col">{t('journal.message')}</th>
                  <th scope="col">{t('journal.auteur')}</th>
                </tr>
              </thead>
              <tbody>
                {events.map((e) => (
                  <tr key={e.id} className={selected === e.id ? 'ligne--active' : undefined}>
                    <td className="mono texte-petit">{formatDateTime(e.created_at, lang)}</td>
                    <td><StatusPill kind={LEVELS[e.level].kind} label={t(LEVELS[e.level].label)} /></td>
                    <td className="texte-secondaire">{e.category}</td>
                    <td>
                      <button type="button" className="lien-ligne" onClick={() => setSelected(e.id)}>{e.message}</button>
                    </td>
                    <td className="texte-secondaire">{e.actor ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        {more && <div className="centre"><button type="button" className="bouton bouton--secondaire" onClick={loadMore}>{t('journal.plus')}</button></div>}
      </div>
      {selected && <Detail eventId={selected} onClose={closeDetail} />}
    </main>
  )
}
