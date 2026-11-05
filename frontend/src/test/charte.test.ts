// frontend/src/test/charte.test.ts
// Contrastes AA de la charte calculés selon WCAG 2.1 sur les vraies variables, et cohérence des deux langues
// @vitest-environment node
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { en } from '../i18n/en'
import { fr } from '../i18n/fr'

const css = readFileSync(new URL('../styles/tokens.css', import.meta.url), 'utf8')

function token(name: string): string {
  const value = css.match(new RegExp(`--${name}:\\s*([^;]+);`))?.[1].trim()
  if (!value) throw new Error(`variable --${name} absente`)
  return value.startsWith('var(') ? token(value.slice(6, -1)) : value
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(token(a)), luminance(token(b))].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

describe('charte graphique', () => {
  it.each([
    ['texte-principal', 'surface-app'], ['texte-secondaire', 'surface-app'], ['texte-tertiaire', 'surface-canevas'],
    ['accent-defaut', 'surface-app'], ['texte-inverse', 'accent-defaut'], ['statut-erreur', 'surface-app'],
    ['statut-marche-texte', 'statut-marche-fond'], ['statut-pause-texte', 'statut-pause-fond'],
    ['statut-arrete-texte', 'statut-arrete-fond'], ['statut-erreur-texte', 'statut-erreur-fond'],
    ['statut-cours-texte', 'statut-cours-fond'], ['texte-inverse', 'bleu-nuit'], ['neutre-300', 'bleu-nuit'],
  ])('%s sur %s atteint 4,5:1', (text, background) => {
    expect(contrast(text, background)).toBeGreaterThanOrEqual(4.5)
  })

  it('reprend les valeurs exactes de la charte', () => {
    expect(token('accent-defaut')).toBe('#3451e8')
    expect(token('texte-principal')).toBe('#121622')
    expect(token('statut-erreur')).toBe('#d6363c')
    expect(token('bleu-nuit')).toBe('#121c34')
  })

  it('le focus reste visible sur le blanc (3:1 pour un élément graphique)', () => {
    expect(contrast('focus', 'surface-app')).toBeGreaterThanOrEqual(3)
  })
})

describe('traductions', () => {
  it('chaque texte garde les mêmes variables en français et en anglais', () => {
    for (const key of Object.keys(fr) as (keyof typeof fr)[]) {
      const vars = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort()
      expect(vars(en[key]), key).toEqual(vars(fr[key]))
      expect(en[key].trim(), key).not.toBe('')
    }
  })
})
