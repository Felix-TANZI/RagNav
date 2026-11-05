// frontend/src/i18n/context.ts
import { createContext, useContext } from 'react'
import type { Key } from './fr'

export type Lang = 'fr' | 'en'
export type Vars = Record<string, string | number>

export interface I18nValue {
  lang: Lang
  setLang: (lang: Lang) => void
  t: (key: Key, vars?: Vars) => string
}

export const I18nContext = createContext<I18nValue | null>(null)

export function useI18n(): I18nValue {
  const value = useContext(I18nContext)
  if (!value) throw new Error('useI18n doit être utilisé dans I18nProvider')
  return value
}
