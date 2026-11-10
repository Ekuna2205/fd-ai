import { useHealth } from '@/hooks/useDashboard'
import { cn } from '@/utils/cn'
import { useT } from '@/i18n'

export function HealthPill() {
  const { data, isLoading, isError } = useHealth()
  const { t } = useT()
  const state = isLoading ? 'checking' : isError ? 'offline' : data?.status === 'ok' ? 'online' : 'degraded'
  const meta = {
    checking: ['bg-muted', 'Checking API'],
    offline: ['bg-danger', 'API offline'],
    degraded: ['bg-warning', 'API degraded'],
    online: ['bg-success', 'API online'],
  }[state]
  return (
    <div role="status" title={t(meta[1])} className="flex items-center gap-2 rounded-full border border-border bg-card px-2.5 py-2 text-xs text-muted sm:px-3 sm:py-1.5">
      <span className={cn('size-2 rounded-full', meta[0], state === 'checking' && 'animate-pulse')} />
      {/* Dot only on phones: the full label pushed the header wider than the screen */}
      <span className="sr-only sm:not-sr-only">{t(meta[1])}</span>
    </div>
  )
}
