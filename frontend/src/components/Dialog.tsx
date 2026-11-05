// frontend/src/components/Dialog.tsx
// Fenêtre accessible, focus gardé à l'intérieur, Échap pour fermer, retour du focus à la fermeture
import { X } from 'lucide-react'
import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useI18n } from '../i18n/context'

interface DialogProps {
  title: string
  description?: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}

const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])'

export function Dialog({ title, description, onClose, children, footer, wide = false }: DialogProps) {
  const { t } = useI18n()
  const titleId = useId()
  const panel = useRef<HTMLDivElement>(null)
  const close = useRef(onClose)
  useEffect(() => {
    close.current = onClose
  }, [onClose])

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null
    const first = panel.current?.querySelector<HTMLElement>('input, select, textarea') ??
      panel.current?.querySelector<HTMLElement>(FOCUSABLE)
    first?.focus()
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close.current()
      if (event.key !== 'Tab' || !panel.current) return
      const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)]
      if (!items.length) return
      const [start, end] = [items[0], items[items.length - 1]]
      if (event.shiftKey && document.activeElement === start) {
        event.preventDefault()
        end.focus()
      } else if (!event.shiftKey && document.activeElement === end) {
        event.preventDefault()
        start.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus()
    }
  }, [])

  return (
    <div className="fenetre-fond" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={panel} className={`fenetre${wide ? ' fenetre--large' : ''}`} role="dialog" aria-modal="true"
        aria-labelledby={titleId}>
        <div className="fenetre__entete">
          <div>
            <h2 id={titleId} className="texte-h2">{title}</h2>
            {description && <p className="texte-secondaire">{description}</p>}
          </div>
          <button type="button" className="bouton bouton--discret bouton--petit" onClick={onClose}
            aria-label={t('action.fermer')} title={t('action.fermer')}>
            <X size={16} aria-hidden="true" />
          </button>
        </div>
        {children}
        {footer && <div className="fenetre__actions">{footer}</div>}
      </div>
    </div>
  )
}

interface ConfirmProps {
  title: string
  message: string
  phrase: string
  confirmLabel: string
  onConfirm: () => Promise<void> | void
  onClose: () => void
}

export function ConfirmDialog({ title, message, phrase, confirmLabel, onConfirm, onClose }: ConfirmProps) {
  const { t } = useI18n()
  const [typed, setTyped] = useState('')
  const [busy, setBusy] = useState(false)
  const inputId = useId()
  const confirm = async () => {
    setBusy(true)
    try {
      await onConfirm()
    } finally {
      setBusy(false)
    }
  }
  return (
    <Dialog title={title} onClose={onClose} footer={
      <>
        <button type="button" className="bouton bouton--secondaire" onClick={onClose}>{t('action.annuler')}</button>
        <button type="button" className="bouton bouton--destructif" disabled={typed !== phrase || busy}
          onClick={confirm}>{confirmLabel}</button>
      </>
    }>
      <p>{message}</p>
      <div className="champ">
        <label htmlFor={inputId}>{t('confirmer.recopier')} <span className="mono">{phrase}</span></label>
        <input id={inputId} value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" />
      </div>
    </Dialog>
  )
}
