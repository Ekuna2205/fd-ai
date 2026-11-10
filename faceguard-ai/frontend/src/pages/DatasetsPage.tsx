import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Database, Loader2, Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { toast } from 'sonner'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Field } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, ErrorState } from '@/components/ui/state'
import { errorMessage } from '@/services/api'
import { createDataset, deleteDataset, listDatasets } from '@/services/datasets'
import type { DatasetSummary } from '@/types/datasets'
import { formatDateTime } from '@/utils/format'
import { useT } from '@/i18n'

export default function DatasetsPage() {
  const { t } = useT()
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [form, setForm] = useState({ name: '', description: '' })
  const [nameErr, setNameErr] = useState<string>()
  const [toDelete, setToDelete] = useState<DatasetSummary | null>(null)
  const list = useQuery({ queryKey: ['datasets'], queryFn: listDatasets, retry: false })
  const create = useMutation({
    mutationFn: () => createDataset(form.name.trim(), form.description.trim()),
    onSuccess: () => { toast.success(t('Dataset created.')); setForm({ name: '', description: '' }); void qc.invalidateQueries({ queryKey: ['datasets'] }) },
    onError: (e) => setNameErr(errorMessage(e)),
  })
  const del = useMutation({
    mutationFn: (id: string) => deleteDataset(id),
    onSuccess: () => { toast.success(t('Dataset deleted.')); setToDelete(null); void qc.invalidateQueries({ queryKey: ['datasets'] }) },
    onError: (e) => { toast.error(errorMessage(e)); setToDelete(null) },
  })
  const submit = (e: FormEvent) => { e.preventDefault(); if (!form.name.trim()) { setNameErr(t('Enter a name.')); return } setNameErr(undefined); create.mutate() }
  const rows = (list.data ?? []).filter((d) => d.name.toLowerCase().includes(search.trim().toLowerCase()))

  return (
    <div className="space-y-6">
      <PageHeader title={t('Datasets')} description={t('Labelled face images for training. Datasets are private to their owner; images are stored by content hash.')} />
      <Card className="p-4"><form onSubmit={submit} className="grid items-end gap-3 sm:grid-cols-[1fr_1.5fr_auto]" noValidate>
        <Field label={t('New dataset name')} value={form.name} maxLength={80} onChange={(e) => setForm((s) => ({ ...s, name: e.target.value }))} error={nameErr} />
        <Field label={t('Description (optional)')} value={form.description} maxLength={500} onChange={(e) => setForm((s) => ({ ...s, description: e.target.value }))} />
        <Button type="submit" disabled={create.isPending}>{create.isPending ? <Loader2 className="size-4 animate-spin" /> : <Plus className="size-4" />}{t('Create')}</Button>
      </form></Card>
      <div className="max-w-sm"><label htmlFor="ds-search" className="mb-1 block text-xs text-muted">{t('Search datasets')}</label><input id="ds-search" value={search} onChange={(e) => setSearch(e.target.value)} className="h-9 w-full rounded-lg border border-border bg-bg px-2.5 text-sm" /></div>
      {list.isError && <ErrorState title={t('Datasets unavailable')} message={errorMessage(list.error)} onRetry={() => void list.refetch()} />}
      {list.isLoading ? <Skeleton className="h-32" /> : rows.length === 0 ? <Card><EmptyState icon={Database} title={search ? t('No datasets match') : t('No datasets yet')} hint={search ? undefined : t('Create one above, then add labelled images.')} /></Card>
        : <div className="grid gap-4 md:grid-cols-2">{rows.map((d) => (
          <Card key={d.id} className="flex flex-col p-5">
            <div className="flex items-start justify-between gap-2"><Link to={`/datasets/${d.id}`} className="font-medium text-primary hover:underline">{d.name}</Link>
              <Button variant="ghost" size="icon" aria-label={t('Delete dataset {name}', { name: d.name })} onClick={() => setToDelete(d)}><Trash2 className="size-4" /></Button></div>
            {d.description && <p className="mt-1 text-sm text-muted">{d.description}</p>}
            <dl className="mt-4 grid grid-cols-4 gap-2 text-center">{([['Images', d.images], ['Real', d.real], ['Fake', d.fake], ['Unlabeled', d.unlabeled]] as const).map(([k, v]) => <div key={k} className="rounded-lg bg-bg py-2"><dt className="text-xs text-muted">{t(k)}</dt><dd className="text-sm font-semibold tabular-nums">{v}</dd></div>)}</dl>
            <p className="mt-3 text-xs text-muted">{t('Updated {when}', { when: formatDateTime(d.updated_at) })}</p>
          </Card>))}</div>}
      <ConfirmDialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)} title={t('Delete “{name}”?', { name: toDelete?.name })} busy={del.isPending}
        description={t('This permanently removes the dataset and its {n} images from the server.', { n: toDelete?.images ?? 0 })} onConfirm={() => toDelete && del.mutate(toDelete.id)} />
    </div>
  )
}
