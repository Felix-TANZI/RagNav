// frontend/src/components/Logo.tsx
// Symbole provisoire des maquettes de la charte, à remplacer ici seul par le fichier officiel du logo
interface LogoProps {
  inverse?: boolean
}

export function Logo({ inverse = false }: LogoProps) {
  return (
    <span className={`logo${inverse ? ' logo--inverse' : ''}`} aria-label="GANDAL">
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
        <rect width="28" height="28" rx="7" fill={inverse ? '#ffffff' : '#121c34'} />
        <g fill={inverse ? '#121c34' : '#ffffff'}>
          <rect x="8" y="8.5" width="12" height="2" rx="1" />
          <rect x="8" y="13" width="12" height="2" rx="1" />
          <rect x="8" y="17.5" width="12" height="2" rx="1" />
        </g>
      </svg>
      <span className="logo__nom" aria-hidden="true">GANDAL</span>
    </span>
  )
}
