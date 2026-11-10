import type { LucideIcon } from 'lucide-react'
import { AlertTriangle } from 'lucide-react'
import type { ReactNode } from 'react'
import { Button } from './button'
import { useT } from '@/i18n'

export function EmptyState({ icon: Icon, title, hint }: { icon: LucideIcon; title: string; hint?: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <div className="grid size-10 place-items-center rounded-lg border border-border bg-bg text-muted">
        <Icon className="size-5" />
      </div>
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="max-w-xs text-xs text-muted">{hint}</p>}
    </div>
  )
}

export function ErrorState({ title, message, onRetry, extra }: { title: string; message: string; onRetry?: () => void; extra?: ReactNode }) {
  const { t } = useT()
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-xl border border-danger/30 bg-danger/5 p-5 sm:flex-row sm:items-center">
      <AlertTriangle className="size-5 shrink-0 text-danger" />
      <div className="flex-1">
        <p className="text-sm font-medium">{title}</p>
        <p className="mt-0.5 text-xs text-muted">{message}</p>
        {extra}
      </div>
      {onRetry && <Button variant="outline" size="sm" onClick={onRetry}>{t('Retry')}</Button>}
    </div>
  )
}
