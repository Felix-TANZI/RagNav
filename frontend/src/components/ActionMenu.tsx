// frontend/src/components/ActionMenu.tsx
// Actions d'une ligne, chacune avec son mot, une action interdite reste visible et dit pourquoi (charte page 30)
import { MoreHorizontal, type LucideIcon } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useI18n } from '../i18n/context'

export interface Action {
  label: string
  icon: LucideIcon
  onSelect: () => void
  destructive?: boolean
  disabledReason?: string
}

export function ActionMenu({ actions, label }: { actions: Action[]; label: string }) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    root.current?.querySelector<HTMLElement>('[role="menuitem"]:not([disabled])')?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    const onClick = (e: MouseEvent) => !root.current?.contains(e.target as Node) && setOpen(false)
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onClick)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onClick)
    }
  }, [open])

  return (
    <div className="menu" ref={root}>
      <button type="button" className="bouton bouton--discret bouton--petit" aria-haspopup="menu" aria-expanded={open}
        aria-label={`${t('action.actions')}, ${label}`} onClick={() => setOpen((v) => !v)}>
        <MoreHorizontal size={16} aria-hidden="true" />{t('action.actions')}
      </button>
      {open && (
        <div className="menu__liste menu__liste--droite" role="menu">
          {actions.map(({ label: text, icon: Icon, onSelect, destructive, disabledReason }) => (
            <button key={text} type="button" role="menuitem" disabled={Boolean(disabledReason)} title={disabledReason}
              className={`menu__item${destructive ? ' menu__item--destructif' : ''}`}
              onClick={() => {
                setOpen(false)
                onSelect()
              }}>
              <Icon size={16} aria-hidden="true" />{text}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
