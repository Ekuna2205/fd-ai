import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, ArrowLeft, CheckCircle2, Download, Loader2, Trash2, UploadCloud } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import { CollectLinkCard } from '@/components/CollectLinkCard'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Pagination } from '@/components/ui/pagination'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, ErrorState } from '@/components/ui/state'
import { errorMessage } from '@/services/api'
import { addImage, deleteDataset, deleteImage, exportDataset, fetchImageBlob, getDataset, getValidation, patchImage } from '@/services/datasets'
import type { DatasetImage } from '@/types/datasets'
import { cn } from '@/utils/cn'
import { translateServer, useT } from '@/i18n'

const PAGE = 24
type Filter = '' | 'REAL' | 'FAKE' | 'UNLABELED'

function Thumb({ id, img }: { id: string; img: DatasetImage }) {
  const { t } = useT()
  const blob = useQuery({ queryKey: ['ds-image', id, img.sha256], queryFn: () => fetchImageBlob(id, img.sha256), staleTime: Infinity, gcTime: 60_000, retry: false })
  const [url, setUrl] = useState<string>()
  useEffect(() => { if (!blob.data) return; const u = URL.createObjectURL(blob.data); setUrl(u); return () => URL.revokeObjectURL(u) }, [blob.data])
  return <div className="grid aspect-square place-items-center overflow-hidden bg-black">{url ? <img src={url} alt={t('Dataset image {id}', { id: img.sha256.slice(0, 8) })} className="size-full object-cover" /> : blob.isError ? <AlertTriangle className="size-5 text-danger" aria-label={t('Failed to load')} /> : <Loader2 className="size-5 animate-spin text-muted" />}</div>
}

export default function DatasetDetailPage() {
  const { t } = useT()
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [filter, setFilter] = useState<Filter>('')
  const [page, setPage] = useState(1)
  const [up, setUp] = useState({ label: '', identity: '', group: '' })
  const [progress, setProgress] = useState<{ done: number; total: number } | null>(null)
  const [failures, setFailures] = useState<string[]>([])
  const [dragging, setDragging] = useState(false)
  const [confirm, setConfirm] = useState<'dataset' | DatasetImage | null>(null)
  const [exporting, setExporting] = useState<'full' | 'face' | null>(null)
  const input = useRef<HTMLInputElement>(null)

  const ds = useQuery({ queryKey: ['dataset', id, filter, page], queryFn: () => getDataset(id, (page - 1) * PAGE, PAGE, filter || undefined), placeholderData: keepPreviousData, retry: false })
  const val = useQuery({ queryKey: ['dataset-validation', id], queryFn: () => getValidation(id), retry: false })
  const refresh = () => { void qc.invalidateQueries({ queryKey: ['dataset', id] }); void qc.invalidateQueries({ queryKey: ['dataset-validation', id] }); void qc.invalidateQueries({ queryKey: ['datasets'] }) }

  const patch = useMutation({ mutationFn: (v: { sha: string; p: Parameters<typeof patchImage>[2] }) => patchImage(id, v.sha, v.p), onSuccess: refresh, onError: (e) => toast.error(errorMessage(e)) })
  const delImg = useMutation({ mutationFn: (sha: string) => deleteImage(id, sha), onSuccess: () => { toast.success(t('Image removed.')); setConfirm(null); refresh() }, onError: (e) => { toast.error(errorMessage(e)); setConfirm(null) } })
  const delDs = useMutation({ mutationFn: () => deleteDataset(id), onSuccess: () => { toast.success(t('Dataset deleted.')); void qc.invalidateQueries({ queryKey: ['datasets'] }); navigate('/datasets', { replace: true }) }, onError: (e) => { toast.error(errorMessage(e)); setConfirm(null) } })

  async function upload(files: FileList | File[]) {
    const list = Array.from(files)
    if (!list.length) return
    setFailures([]); setProgress({ done: 0, total: list.length })
    const bad: string[] = []
    for (const [i, f] of list.entries()) {
      try { await addImage(id, f, up) } catch (e) { bad.push(`${f.name}: ${errorMessage(e)}`) }
      setProgress({ done: i + 1, total: list.length })
    }
    setFailures(bad); setProgress(null); refresh()
    const ok = list.length - bad.length
    if (ok) toast.success(t('{n} image(s) added.', { n: ok }))
    if (input.current) input.current.value = ''
  }

  async function doExport(crop: 'full' | 'face') {
    setExporting(crop)
    try {
      await exportDataset(id, crop)
      toast.success(crop === 'face'
        ? t('Face-crop export downloaded. Images without exactly one face and unlabeled images are skipped. Register the trained model with input "face crop".')
        : t('Export downloaded (unlabeled images are skipped).'))
    } catch (e) { toast.error(errorMessage(e)) } finally { setExporting(null) }
  }

  if (ds.isError && !ds.data) return <div className="space-y-4"><Link to="/datasets" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="size-4" />{t('Datasets')}</Link><ErrorState title={t('Dataset unavailable')} message={errorMessage(ds.error)} onRetry={() => void ds.refetch()} /></div>
  const d = ds.data

  return (
    <div className="space-y-6">
      <Link to="/datasets" className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-fg"><ArrowLeft className="size-4" />{t('Datasets')}</Link>
      <PageHeader title={d?.name ?? t('Dataset')} description={d?.description || undefined}
        actions={<><Button variant="outline" onClick={() => void doExport('full')} disabled={!!exporting || !d?.images}><Download className="size-4" />{exporting === 'full' ? t('Preparing…') : t('Export ZIP')}</Button>
          <Button variant="outline" onClick={() => void doExport('face')} disabled={!!exporting || !d?.images} title={t('One square face crop per image, as used by face-crop models')}><Download className="size-4" />{exporting === 'face' ? t('Cropping…') : t('Export face crops')}</Button>
          <Button variant="outline" onClick={() => setConfirm('dataset')}><Trash2 className="size-4" />{t('Delete')}</Button></>} />

      {d && <CollectLinkCard dataset={d} onChange={refresh} />}

      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title={t('Add images')} description={t('JPG or PNG. Labels and identity apply to every file you add now; you can edit each image later.')} />
          <div className="space-y-4 p-5">
            <div className="grid gap-3 sm:grid-cols-3">
              <Select label={t('Label')} value={up.label} onChange={(e) => setUp((s) => ({ ...s, label: e.target.value }))}><option value="">{t('Unlabeled')}</option><option value="REAL">{t('Real (bona fide)')}</option><option value="FAKE">{t('Fake (attack)')}</option></Select>
              <div><label htmlFor="up-id" className="mb-1 block text-xs text-muted">{t('Identity (person ID)')}</label><input id="up-id" maxLength={64} value={up.identity} onChange={(e) => setUp((s) => ({ ...s, identity: e.target.value }))} className="h-9 w-full rounded-lg border border-border bg-bg px-2.5 text-sm" /></div>
              <div><label htmlFor="up-group" className="mb-1 block text-xs text-muted">{t('Group (optional)')}</label><input id="up-group" maxLength={64} value={up.group} onChange={(e) => setUp((s) => ({ ...s, group: e.target.value }))} className="h-9 w-full rounded-lg border border-border bg-bg px-2.5 text-sm" /></div>
            </div>
            <div role="button" tabIndex={0} aria-label={t('Choose images to add')} onClick={() => input.current?.click()} onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && input.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={(e) => { e.preventDefault(); setDragging(false); void upload(e.dataTransfer.files) }}
              className={cn('flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-4 py-8 text-center text-sm', dragging ? 'border-primary bg-primary/5' : 'border-border hover:border-muted/50')}>
              <UploadCloud className="size-7 text-primary" /><p>{t('Drag images here, or click to browse')}</p>
              <input ref={input} type="file" hidden multiple accept=".jpg,.jpeg,.png" onChange={(e) => e.target.files && void upload(e.target.files)} /></div>
            {progress && <p role="status" className="flex items-center gap-2 text-sm text-muted"><Loader2 className="size-4 animate-spin" />{t('Uploading {done} / {total}…', { done: progress.done, total: progress.total })}</p>}
            {failures.length > 0 && <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 p-3 text-xs text-danger"><p className="font-medium">{t('{n} file(s) not added', { n: failures.length })}</p><ul className="mt-1 list-disc pl-4">{failures.slice(0, 8).map((f) => <li key={f}>{f}</li>)}</ul></div>}
          </div>
        </Card>
        <Card>
          <CardHeader title={t('Readiness')} description={t('Checks before training')} />
          <div className="space-y-3 p-5 text-sm">
            {val.isLoading ? <Skeleton className="h-20" /> : val.data ? <>
              <p className={cn('flex items-center gap-2 font-medium', val.data.ready ? 'text-success' : 'text-warning')}>{val.data.ready ? <CheckCircle2 className="size-4" /> : <AlertTriangle className="size-4" />}{val.data.ready ? t('Ready for training') : t('Not ready for training')}</p>
              {val.data.problems.length > 0 && <ul className="list-disc space-y-1 pl-4 text-xs text-warning">{val.data.problems.map((p) => <li key={p}>{translateServer(p)}</li>)}</ul>}
              {val.data.warnings.length > 0 && <ul className="list-disc space-y-1 pl-4 text-xs text-muted">{val.data.warnings.map((p) => <li key={p}>{translateServer(p)}</li>)}</ul>}
              <dl className="grid grid-cols-2 gap-2 border-t border-border pt-3 text-xs">{([['Images', val.data.stats.images], ['Identities', val.data.stats.identities], ['Real', val.data.stats.labels.REAL], ['Fake', val.data.stats.labels.FAKE], ['Unlabeled', val.data.stats.labels.UNLABELED], ['No identity', val.data.stats.images_without_identity]] as const).map(([k, v]) => <div key={k}><dt className="text-muted">{t(k)}</dt><dd className="font-medium tabular-nums">{v}</dd></div>)}</dl></> : null}
          </div>
        </Card>
      </section>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-3"><h2 className="text-sm font-semibold">{t('Images')} {d && <span className="font-normal text-muted">({d.total_filtered})</span>}</h2>
          <div className="w-40"><Select label={t('Filter')} value={filter} onChange={(e) => { setFilter(e.target.value as Filter); setPage(1) }}><option value="">{t('All')}</option><option value="REAL">{t('Real')}</option><option value="FAKE">{t('Fake')}</option><option value="UNLABELED">{t('Unlabeled')}</option></Select></div></div>
        {ds.isLoading ? <div className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4 lg:grid-cols-6">{Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="aspect-square" />)}</div>
          : d && d.items.length > 0 ? <>
            <ul className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-3 lg:grid-cols-6">{d.items.map((img) => (
              <li key={img.sha256} className="overflow-hidden rounded-lg border border-border">
                <Thumb id={id} img={img} />
                <div className="space-y-1.5 p-2">
                  <select aria-label={t('Label for {id}', { id: img.sha256.slice(0, 8) })} value={img.label ?? ''} onChange={(e) => patch.mutate({ sha: img.sha256, p: { label: (e.target.value || null) as 'REAL' | 'FAKE' | null } })} className="h-7 w-full rounded-md border border-border bg-bg px-1 text-xs">
                    <option value="">{t('Unlabeled')}</option><option value="REAL">{t('Real')}</option><option value="FAKE">{t('Fake')}</option></select>
                  <input aria-label={t('Identity for {id}', { id: img.sha256.slice(0, 8) })} defaultValue={img.identity ?? ''} placeholder={t('identity')} maxLength={64} onBlur={(e) => { const v = e.target.value.trim() || null; if (v !== img.identity) patch.mutate({ sha: img.sha256, p: { identity: v } }) }} className="h-7 w-full rounded-md border border-border bg-bg px-1.5 text-xs" />
                  <div className="flex items-center justify-between text-[11px] text-muted"><span>{img.width}×{img.height}</span><button aria-label={t('Remove image {id}', { id: img.sha256.slice(0, 8) })} onClick={() => setConfirm(img)} className="cursor-pointer text-danger hover:underline">{t('Remove')}</button></div>
                </div></li>))}</ul>
            <Pagination page={page} pageSize={PAGE} total={d.total_filtered} onPage={setPage} /></>
          : <EmptyState icon={UploadCloud} title={filter ? t('No images with this label') : t('No images yet')} hint={filter ? undefined : t('Add labelled images above.')} />}
      </Card>

      <ConfirmDialog open={confirm === 'dataset'} onOpenChange={(o) => !o && setConfirm(null)} title={t('Delete this dataset?')} description={t('The dataset and all of its images are permanently removed.')} busy={delDs.isPending} onConfirm={() => delDs.mutate()} />
      <ConfirmDialog open={!!confirm && confirm !== 'dataset'} onOpenChange={(o) => !o && setConfirm(null)} title={t('Remove this image?')} confirmLabel={t('Remove')} description={t('The image file is securely deleted from the server.')} busy={delImg.isPending} onConfirm={() => confirm && confirm !== 'dataset' && delImg.mutate(confirm.sha256)} />
    </div>
  )
}
