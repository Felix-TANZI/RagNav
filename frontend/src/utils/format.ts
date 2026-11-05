// frontend/src/utils/format.ts
import type { Lang } from '../i18n/context'

const LOCALES: Record<Lang, string> = { fr: 'fr-FR', en: 'en-GB' }

export function formatDate(value: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALES[lang], { day: 'numeric', month: 'long', year: 'numeric' })
    .format(new Date(value))
}

export function formatDateTime(value: string, lang: Lang): string {
  return new Intl.DateTimeFormat(LOCALES[lang], { dateStyle: 'short', timeStyle: 'medium' }).format(new Date(value))
}

export function formatSize(bytes: number, lang: Lang): string {
  const units = lang === 'fr' ? ['o', 'Ko', 'Mo', 'Go'] : ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unit = 0
  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }
  return `${new Intl.NumberFormat(LOCALES[lang], { maximumFractionDigits: unit ? 1 : 0 }).format(size)} ${units[unit]}`
}
