// frontend/src/i18n/I18n.tsx
// Interface en français et en anglais (charte, critère WCAG 3.1.1), la langue est déclarée sur la page
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { I18nContext, type Lang, type Vars } from './context'
import { en } from './en'
import { fr, type Key } from './fr'

const DICTIONARIES: Record<Lang, Record<Key, string>> = { fr, en }
const STORAGE_KEY = 'gandal-langue'

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved === 'en' ? 'en' : 'fr'
  } catch {
    return 'fr'
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((next: Lang) => {
    setLangState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      return
    }
  }, [])

  const t = useCallback(
    (key: Key, vars?: Vars) =>
      DICTIONARIES[lang][key].replace(/\{(\w+)\}/g, (_, name: string) => String(vars?.[name] ?? `{${name}}`)),
    [lang],
  )

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t])
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}
