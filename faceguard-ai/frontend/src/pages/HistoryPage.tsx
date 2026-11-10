import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, ArrowUp, Download, History, Search, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { PageHeader } from '@/components/PageHeader'
import { StatusBadge } from '@/components/StatusBadge'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Pagination } from '@/components/ui/pagination'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, ErrorState } from '@/components/ui/state'
import { useDebounced } from '@/hooks/useDebounced'
import { errorMessage } from '@/services/api'
import { deleteVerification, exportVerifications, listVerifications } from '@/services/history'
import type { HistoryQuery } from '@/types/history'
import { formatDateTime, formatMs, formatPercent } from '@/utils/format'
import { useT } from '@/i18n'
import { statusLabel } from '@/i18n/labels'
import { spoofLabel } from '@/i18n/labels'

const MODES = { LIVE: 'Live camera', UPLOAD_IMAGE: 'Image upload', UPLOAD_VIDEO: 'Video upload' } as const
const STATUSES = ['REAL', 'FAKE', 'UNCERTAIN', 'NO_FACE', 'MULTIPLE_FACES', 'PROCESSING', 'ERROR'] as const
type SortKey = HistoryQuery['sort']

export default function HistoryPage() {
  const { t } = useT()
  const qc = useQueryClient()
  const [f, setF] = useState<Omit<HistoryQuery, 'q'>>({ sort: 'created_at', order: 'desc', page: 1, page_size: 20, status: '', mode: '', date_from: '', date_to: '' })
  const [text, setText] = useState('')
  const q = useDebounced(text.trim())
  const query: HistoryQuery = { ...f, q }
  const [toDelete, setToDelete] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const list = useQuery({ queryKey: ['history', query], queryFn: () => listVerifications(query), placeholderData: keepPreviousData, retry: false })
  const del = useMutation({
    mutationFn: deleteVerification,
    onSuccess: () => { toast.success(t('Verification deleted.')); setToDelete(null); void qc.invalidateQueries({ queryKey: ['history'] }); void qc.invalidateQueries({ queryKey: ['dashboard'] }) },
    onError: (e) => { toast.error(errorMessage(e)); setToDelete(null) },
  })

  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((s) => ({ ...s, [k]: v, page: k === 'page' ? (v as number) : 1 }))
  const sortBy = (k: SortKey) => setF((s) => ({ ...s, sort: k, order: s.sort === k && s.order === 'desc' ? 'asc' : 'desc', page: 1 }))
  const filtered = !!(q || f.status || f.mode || f.date_from || f.date_to)
  const reset = () => { setText(''); setF((s) => ({ ...s, status: '', mode: '', date_from: '', date_to: '', page: 1 })) }

  async function doExport() {
    setExporting(true)
    try { await exportVerifications(query); toast.success(t('Export downloaded.')) } catch (e) { toast.error(errorMessage(e)) } finally { setExporting(false) }
  }

  const Th = ({ k, children, right }: { k?: SortKey; children: string; right?: boolean }) => (
    <th scope="col" aria-sort={k && f.sort === k ? (f.order === 'asc' ? 'ascending' : 'descending') : undefined} className={`px-4 py-2.5 font-medium ${right ? 'text-right' : ''}`}>
      {k ? <button onClick={() => sortBy(k)} className="inline-flex cursor-pointer items-center gap-1 hover:text-fg">{children}{f.sort === k && (f.order === 'asc' ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}</button> : children}
    </th>
  )

  return (
    <div className="space-y-6">
      <PageHeader title={t('Verification history')} description={t('Your own verifications. Other users\' records are never shown here.')}
        actions={<Button variant="outline" onClick={doExport} disabled={exporting || !list.data?.total}><Download className="size-4" />{exporting ? t('Exporting…') : t('Export CSV')}</Button>} />

      <Card className="p-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <div className="sm:col-span-2 lg:col-span-1">
            <label htmlFor="hist-search" className="mb-1 block text-xs text-muted">{t('Search')}</label>
            <div className="relative"><Search className="absolute left-2.5 top-2.5 size-4 text-muted" />
              <input id="hist-search" value={text} onChange={(e) => { setText(e.target.value); setF((s) => ({ ...s, page: 1 })) }} placeholder={t('ID or text…')} maxLength={64}
                className="h-9 w-full rounded-lg border border-border bg-bg pl-8 pr-2 text-sm" /></div>
          </div>
          <Select label={t('Status')} value={f.status} onChange={(e) => set('status', e.target.value as typeof f.status)}><option value="">{t('All')}</option>{STATUSES.map((s) => <option key={s} value={s}>{statusLabel(s)}</option>)}</Select>
          <Select label={t('Source')} value={f.mode} onChange={(e) => set('mode', e.target.value as typeof f.mode)}><option value="">{t('All')}</option>{Object.entries(MODES).map(([k, v]) => <option key={k} value={k}>{t(v)}</option>)}</Select>
          <div><label htmlFor="hist-from" className="mb-1 block text-xs text-muted">{t('From')}</label><input id="hist-from" type="date" value={f.date_from} max={f.date_to || undefined} onChange={(e) => set('date_from', e.target.value)} className="h-9 w-full rounded-lg border border-border bg-bg px-2 text-sm" /></div>
          <div><label htmlFor="hist-to" className="mb-1 block text-xs text-muted">{t('To')}</label><input id="hist-to" type="date" value={f.date_to} min={f.date_from || undefined} onChange={(e) => set('date_to', e.target.value)} className="h-9 w-full rounded-lg border border-border bg-bg px-2 text-sm" /></div>
        </div>
        {filtered && <Button variant="ghost" size="sm" className="mt-3" onClick={reset}>{t('Clear filters')}</Button>}
      </Card>

      {list.isError && <ErrorState title={t('History is unavailable')} message={errorMessage(list.error)} onRetry={() => void list.refetch()} />}

      <Card className="overflow-hidden">
        {list.isLoading ? <div className="space-y-3 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-5" />)}</div>
          : list.data && list.data.items.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead className="border-b border-border text-xs text-muted"><tr>
                    <Th k="created_at">{t('Time')}</Th><Th k="status">{t('Status')}</Th><Th>{t('Source')}</Th><Th>{t('Spoof type')}</Th>
                    <Th k="confidence" right>{t('Confidence')}</Th><Th right>{t('Faces')}</Th><Th k="processing_ms" right>{t('Duration')}</Th><th className="px-4 py-2.5"><span className="sr-only">{t('Actions')}</span></th>
                  </tr></thead>
                  <tbody className="divide-y divide-border">
                    {list.data.items.map((r) => (
                      <tr key={r.id} className="hover:bg-card-hover/50">
                        <td className="px-4 py-3"><Link to={`/verifications/${r.id}`} className="text-primary hover:underline">{formatDateTime(r.created_at)}</Link></td>
                        <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                        <td className="px-4 py-3 text-muted">{t(MODES[r.mode])}</td>
                        <td className="px-4 py-3 text-muted">{spoofLabel(r.spoof_type)}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{r.confidence == null ? '—' : formatPercent(r.confidence)}</td>
                        <td className="px-4 py-3 text-right tabular-nums">{r.face_count ?? '—'}</td>
                        <td className="px-4 py-3 text-right tabular-nums text-muted">{formatMs(r.processing_ms)}</td>
                        <td className="px-4 py-3 text-right"><Button variant="ghost" size="icon" aria-label={t('Delete verification from {when}', { when: formatDateTime(r.created_at) })} onClick={() => setToDelete(r.id)}><Trash2 className="size-4" /></Button></td>
                      </tr>))}
                  </tbody>
                </table>
              </div>
              <Pagination page={list.data.page} pageSize={list.data.page_size} total={list.data.total} onPage={(p) => set('page', p)} />
            </>
          ) : <EmptyState icon={History} title={filtered ? t('No verifications match these filters') : t('No verifications yet')}
              hint={filtered ? t('Try a different search or clear the filters.') : t('Run a live verification or upload a file and it will appear here.')} />}
      </Card>

      <ConfirmDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)} title={t('Delete this verification?')}
        description={t('The stored result will be permanently removed. This cannot be undone.')} busy={del.isPending} onConfirm={() => toDelete && del.mutate(toDelete)} />
    </div>
  )
}
