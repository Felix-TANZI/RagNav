// frontend/src/components/Toast.tsx
// Message bref de succès en bas de l'écran (charte page 32), annoncé aux lecteurs d'écran
import { CircleCheck } from 'lucide-react'
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { ToastContext } from './toastContext'

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const show = useCallback((text: string) => {
    window.clearTimeout(timer.current)
    setMessage(text)
    timer.current = window.setTimeout(() => setMessage(null), 4000)
  }, [])
  useEffect(() => () => window.clearTimeout(timer.current), [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div role="status" aria-live="polite">
        {message && (
          <div className="toast">
            <CircleCheck size={16} aria-hidden="true" />
            {message}
          </div>
        )}
      </div>
    </ToastContext.Provider>
  )
}
