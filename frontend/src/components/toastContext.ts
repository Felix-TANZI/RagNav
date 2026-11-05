// frontend/src/components/toastContext.ts
import { createContext, useContext } from 'react'

export const ToastContext = createContext<(message: string) => void>(() => undefined)

export function useToast(): (message: string) => void {
  return useContext(ToastContext)
}
