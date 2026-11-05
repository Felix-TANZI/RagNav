// frontend/src/pages/Accueil.tsx
// Accueil de l'espace client sur le modèle de l'écran GANDAL, salutation, état des services et carte de l'assistant
import { FileSearch, ListChecks, Network, RotateCcw, SendHorizontal, Server, Sparkles, Square } from 'lucide-react'
import { useEffect, useId, useRef, useState, type SubmitEvent } from 'react'
import type { ApiError } from '../api/client'
import { streamChat } from '../api/stream'
import type { Source } from '../api/types'
import { useAuth } from '../auth/context'
import { AnswerText, SourceList } from '../components/Answer'
import { ErrorBanner } from '../components/Feedback'
import { ServiceStatus } from '../components/ServiceStatus'
import { StatusPill } from '../components/StatusPill'
import { useI18n } from '../i18n/context'
import type { Key } from '../i18n/fr'

const MAX_CHARS = 1000

interface Message {
  id: number
  question: string
  text: string
  step: 'recherche' | 'redaction' | null
  state: 'running' | 'done' | 'stopped' | 'error'
  found: boolean
  sources: Source[]
  error: ApiError | null
}

const SHORTCUTS: { label: Key; starter: Key; icon: typeof Network }[] = [
  { label: 'raccourci.port', starter: 'raccourci.port.debut', icon: Network },
  { label: 'raccourci.procedure', starter: 'raccourci.procedure.debut', icon: ListChecks },
  { label: 'raccourci.document', starter: 'raccourci.document.debut', icon: FileSearch },
  { label: 'raccourci.machine', starter: 'raccourci.machine.debut', icon: Server },
]

function displayName(name: string, email: string): string {
  return name.trim() || email.split('@')[0]
}

export function Accueil() {
  const { user } = useAuth()
  const { t } = useI18n()
  const [messages, setMessages] = useState<Message[]>([])
  const [question, setQuestion] = useState('')
  const [announce, setAnnounce] = useState('')
  const [hour] = useState(() => new Date().getHours())
  const input = useRef<HTMLInputElement>(null)
  const controller = useRef<AbortController | null>(null)
  const nextId = useRef(1)
  const inputId = useId()
  const running = messages.some((m) => m.state === 'running')
  const name = user ? displayName(user.name, user.email) : ''

  useEffect(() => () => controller.current?.abort(), [])

  const update = (id: number, patch: Partial<Message>) =>
    setMessages((list) => list.map((m) => (m.id === id ? { ...m, ...patch } : m)))

  const ask = (text: string) => {
    const id = nextId.current++
    setMessages((list) => [...list, { id, question: text, text: '', step: 'recherche', state: 'running',
      found: true, sources: [], error: null }])
    setAnnounce('')
    const abort = new AbortController()
    controller.current = abort
    void streamChat(text, {
      onStep: (step) => update(id, { step: step === 'redaction' ? 'redaction' : 'recherche' }),
      onText: (piece) => setMessages((list) => list.map((m) => (m.id === id ? { ...m, text: m.text + piece } : m))),
      onDone: (result) => {
        update(id, { text: result.answer, found: result.found, sources: result.sources, state: 'done', step: null })
        setAnnounce(t('assistant.reponsePrete'))
      },
      onError: (error) => update(id, { error, state: 'error', step: null }),
    }, abort.signal)
  }

  const submit = (event: SubmitEvent<HTMLFormElement>) => {
    event.preventDefault()
    const text = question.trim()
    if (!text || running || text.length > MAX_CHARS) return
    setQuestion('')
    ask(text)
  }

  const stop = () => {
    controller.current?.abort()
    setMessages((list) => list.map((m) => (m.state === 'running' ? { ...m, state: 'stopped', step: null } : m)))
  }

  const applyShortcut = (starter: Key) => {
    setQuestion(t(starter))
    input.current?.focus()
  }

  const tooLong = question.trim().length > MAX_CHARS
  return (
    <main className="page page--accueil">
      <div className="accueil">
        <ServiceStatus />
        <h1 className="texte-display">{t(hour < 18 ? 'accueil.bonjour' : 'accueil.bonsoir', { nom: name })}</h1>
        <p className="texte-secondaire accueil__resume">{t('accueil.resume')}</p>

        <section className="carte assistant" aria-labelledby="titre-assistant">
          <div className="assistant__entete">
            <span className="assistant__icone"><Sparkles size={20} aria-hidden="true" /></span>
            <div className="assistant__titres">
              <h2 id="titre-assistant" className="texte-h3">{t('assistant.titre')}</h2>
              <p className="texte-petit texte-secondaire">{t('assistant.sousTitre')}</p>
            </div>
            {messages.length > 0 && !running && (
              <button type="button" className="bouton bouton--discret bouton--petit" onClick={() => setMessages([])}>
                <RotateCcw size={16} aria-hidden="true" />{t('assistant.nouvelle')}
              </button>
            )}
          </div>

          <div className="conversation">
            <div className="bulle bulle--assistant">
              <Sparkles size={16} aria-hidden="true" className="bulle__icone" />
              <p>{t('assistant.accueil', { nom: name })}</p>
            </div>
            {messages.map((m) => (
              <div key={m.id} className="echange">
                <p className="bulle bulle--question">{m.question}</p>
                <article className="reponse" aria-busy={m.state === 'running'}>
                  {m.step && (
                    <StatusPill kind="cours"
                      label={t(m.step === 'recherche' ? 'assistant.etape.recherche' : 'assistant.etape.redaction')} />
                  )}
                  {!m.found && m.state === 'done' && <StatusPill kind="arrete" label={t('assistant.absent')} />}
                  {m.text && <AnswerText text={m.text} sources={m.sources} idPrefix={`source-${m.id}`} />}
                  {m.state === 'stopped' && <p className="texte-legende">{t('assistant.interrompue')}</p>}
                  {m.state === 'done' && <SourceList sources={m.sources} idPrefix={`source-${m.id}`} />}
                  {m.error && <ErrorBanner error={m.error} onRetry={running ? undefined : () => ask(m.question)} />}
                </article>
              </div>
            ))}
          </div>

          <form className="assistant__saisie" onSubmit={submit}>
            <label htmlFor={inputId} className="visuellement-cache">{t('assistant.libelle')}</label>
            <input id={inputId} ref={input} className="assistant__champ" value={question}
              onChange={(e) => setQuestion(e.target.value)} placeholder={t('assistant.placeholder')}
              autoComplete="off" aria-invalid={tooLong} aria-describedby={tooLong ? `${inputId}-erreur` : undefined} />
            {running ? (
              <button type="button" className="bouton bouton--secondaire" onClick={stop}>
                <Square size={16} aria-hidden="true" />{t('assistant.arreter')}
              </button>
            ) : (
              <button type="submit" className="bouton bouton--principal" disabled={!question.trim() || tooLong}>
                <SendHorizontal size={16} aria-hidden="true" />{t('assistant.envoyer')}
              </button>
            )}
          </form>
          {tooLong && <p id={`${inputId}-erreur`} className="champ__erreur">{t('assistant.trop', { max: MAX_CHARS })}</p>}
          <p className="visuellement-cache" aria-live="polite">{announce}</p>
        </section>

        <div className="raccourcis">
          {SHORTCUTS.map(({ label, starter, icon: Icon }) => (
            <button key={label} type="button" className="raccourci" onClick={() => applyShortcut(starter)}>
              <Icon size={16} aria-hidden="true" />{t(label)}
            </button>
          ))}
        </div>
      </div>
    </main>
  )
}
