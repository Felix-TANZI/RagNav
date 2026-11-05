// frontend/src/components/StatusPill.tsx
// Un statut porte toujours une pastille et un mot, jamais la couleur seule (charte page 10, WCAG 1.4.1)
export type StatusKind = 'marche' | 'pause' | 'arrete' | 'erreur' | 'cours'

export function StatusPill({ kind, label }: { kind: StatusKind; label: string }) {
  return <span className={`puce puce--${kind}`}>{label}</span>
}
