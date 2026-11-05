// frontend/src/components/Answer.tsx
// Réponse de l'assistant, citations [n] reliées à la source n, sources ouvrables à leur page
import { ExternalLink, FileText } from 'lucide-react'
import { useState } from 'react'
import type { Source } from '../api/types'
import { useI18n } from '../i18n/context'
import { openDocument } from '../utils/documents'
import { ErrorBanner } from './Feedback'

const TOKENS = /(\[\d+\]|`[^`]+`)/g

export function AnswerText({ text, sources, idPrefix }: { text: string; sources: Source[]; idPrefix: string }) {
  const { t } = useI18n()
  return (
    <div className="reponse__texte">
      {text.split(TOKENS).map((part, i) => {
        const citation = part.match(/^\[(\d+)\]$/)
        if (citation) {
          const number = Number(citation[1])
          const source = sources[number - 1]
          if (!source) return <span key={i}>{part}</span>
          return (
            <a key={i} className="citation" href={`#${idPrefix}-${number}`}
              aria-label={t('assistant.citation', { n: number, titre: source.title })}>
              {number}
            </a>
          )
        }
        if (part.startsWith('`') && part.endsWith('`') && part.length > 2) {
          return <code key={i} className="mono code-en-ligne">{part.slice(1, -1)}</code>
        }
        return <span key={i}>{part}</span>
      })}
    </div>
  )
}

export function SourceList({ sources, idPrefix }: { sources: Source[]; idPrefix: string }) {
  const { t } = useI18n()
  const [error, setError] = useState<unknown>(null)
  if (!sources.length) return null
  return (
    <div className="sources">
      <p className="texte-legende">{t('assistant.sources')}</p>
      <ol className="sources__liste">
        {sources.map((source, i) => (
          <li key={`${source.document_id}-${i}`} id={`${idPrefix}-${i + 1}`} className="source" tabIndex={-1}>
            <span className="source__numero" aria-hidden="true">{i + 1}</span>
            <FileText size={16} aria-hidden="true" className="source__icone" />
            <div className="source__texte">
              <span className="texte-fort">{source.title}</span>
              <span className="texte-legende">
                {[source.section, source.page ? t('assistant.page', { page: source.page }) : null,
                  t('assistant.version', { version: source.version })].filter(Boolean).join(' · ')}
              </span>
            </div>
            <button type="button" className="bouton bouton--discret bouton--petit"
              onClick={() => openDocument(`/documents/${source.document_id}/file`, source.page).catch(setError)}>
              <ExternalLink size={16} aria-hidden="true" />
              {t('assistant.ouvrir')}
            </button>
          </li>
        ))}
      </ol>
      {error !== null && <ErrorBanner error={error} />}
    </div>
  )
}
