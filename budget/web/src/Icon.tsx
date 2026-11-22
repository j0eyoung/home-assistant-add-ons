// One small stroke icon set (24px grid, 2px round strokes) so the UI never
// leans on text glyphs for arrows, checks or warnings.
const PATHS = {
  'arrow-right': 'M5 12h14M13 6l6 6-6 6',
  up: 'M12 19V5M6 11l6-6 6 6',
  down: 'M12 5v14M6 13l6 6 6-6',
  equal: 'M5 9h14M5 15h14',
  check: 'M5 12.5l4.5 4.5L19 7',
  warning: 'M12 3.5L21.5 20h-19L12 3.5zM12 10v4.5M12 17.5v.01',
  split: 'M6 4v6a4 4 0 0 0 4 4h9M15 10l4 4-4 4',
  more: 'M5 12h.01M12 12h.01M19 12h.01',
} as const

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 16, label }: { name: IconName; size?: number; label?: string }) {
  return (
    <svg className={`icon icon-${name}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={name === 'more' ? 3.5 : 2} strokeLinecap="round" strokeLinejoin="round"
      role={label ? 'img' : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <path d={PATHS[name]} />
    </svg>
  )
}
