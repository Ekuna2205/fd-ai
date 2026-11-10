import { Check, X } from 'lucide-react'
import type { Quality, QualityCheck } from '@/types/face'
import { cn } from '@/utils/cn'
import { translateServer, useT } from '@/i18n'

function value(c: QualityCheck, t: (s: string, v?: Record<string, number>) => string): string {
  if (c.value == null) return ''
  switch (c.name) {
    case 'size': return t('{pct}% of width', { pct: Math.round(c.value * 100) })
    case 'brightness': return `${Math.round(c.value)}/255`
    case 'roll': return `${Math.round(c.value)}°`
    case 'position': return ''
    default: return String(Math.round(c.value))
  }
}

export function QualityList({ quality }: { quality: Quality | null }) {
  const { t } = useT()
  if (!quality) return <p className="px-5 py-6 text-sm text-muted">{t('Quality is assessed when exactly one face is visible.')}</p>
  return (
    <ul className="divide-y divide-border">
      {quality.checks.map((c) => (
        <li key={c.name} className="flex items-center gap-3 px-5 py-2.5 text-sm">
          <span className={cn('grid size-5 shrink-0 place-items-center rounded-full', c.ok ? 'bg-success/15 text-success' : 'bg-warning/15 text-warning')}>
            {c.ok ? <Check className="size-3" /> : <X className="size-3" />}
          </span>
          <span className="flex-1">{translateServer(c.label)}{!c.ok && c.message && <span className="block text-xs text-muted">{translateServer(c.message)}</span>}</span>
          <span className="text-xs tabular-nums text-muted">{value(c, t)}</span>
        </li>
      ))}
    </ul>
  )
}
