import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from './button'
import { useT } from '@/i18n'

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const { t } = useT()
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  return (
    <nav aria-label={t('Pagination')} className="flex items-center justify-between gap-3 border-t border-border px-4 py-3 text-sm">
      <p className="text-muted tabular-nums">{t('{from}–{to} of {total}', { from, to: Math.min(page * pageSize, total), total })}</p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="icon" aria-label={t('Previous page')} disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft className="size-4" /></Button>
        <span className="min-w-16 text-center tabular-nums text-muted">{page} / {pages}</span>
        <Button variant="outline" size="icon" aria-label={t('Next page')} disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight className="size-4" /></Button>
      </div>
    </nav>
  )
}
