import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Boxes, Check, ChevronDown, Copy, Info, Trash2, Upload } from 'lucide-react'
import { useMemo, useState, type FormEvent } from 'react'
import { toast } from 'sonner'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { ConfirmDialog } from '@/components/ui/confirm-dialog'
import { Field } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, ErrorState } from '@/components/ui/state'
import { useAuth } from '@/hooks/useAuth'
import { errorMessage } from '@/services/api'
import { listDatasets, getValidation } from '@/services/datasets'
import { activateModel, deactivateModel, deleteModel, getModel, listModels, registerModel } from '@/services/models'
import type { ModelInfo } from '@/types/models'
import { cn } from '@/utils/cn'
import { formatDateTime, formatPercent } from '@/utils/format'
import { translateServer, useT } from '@/i18n'

const METRICS = [['apcer', 'APCER'], ['bpcer', 'BPCER'], ['acer', 'ACER'], ['roc_auc', 'ROC-AUC'], ['accuracy', 'Accuracy'], ['precision', 'Precision'], ['recall', 'Recall'], ['f1', 'F1']] as const

function History({ id }: { id: string }) {
  const { t } = useT()
  const d = useQuery({ queryKey: ['model', id], queryFn: () => getModel(id), retry: false })
  if (d.isLoading) return <Skeleton className="m-4 h-16" />
  if (d.isError) return <p className="p-4 text-sm text-danger">{errorMessage(d.error)}</p>
  if (!d.data?.evaluations.length) return <p className="p-4 text-sm text-muted">{t('No evaluations have been recorded for this model.')}</p>
  return <div className="overflow-x-auto"><table className="w-full min-w-[620px] text-left text-xs"><thead className="text-muted"><tr>{['Evaluated', 'Samples', 'Threshold', 'APCER', 'BPCER', 'ACER', 'ROC-AUC', 'Identity-disjoint'].map((h) => <th key={h} scope="col" className="px-4 py-2 font-medium">{/^[A-Z-]+$/.test(h) ? h : t(h)}</th>)}</tr></thead>
    <tbody className="divide-y divide-border">{d.data.evaluations.map((e) => <tr key={e.id}><td className="px-4 py-2">{formatDateTime(e.evaluated_at)}</td><td className="px-4 py-2 tabular-nums">{e.sample_count ?? '—'}</td><td className="px-4 py-2 tabular-nums">{e.threshold ?? '—'}</td>
      <td className="px-4 py-2 tabular-nums">{formatPercent(e.apcer)}</td><td className="px-4 py-2 tabular-nums">{formatPercent(e.bpcer)}</td><td className="px-4 py-2 tabular-nums">{formatPercent(e.acer)}</td><td className="px-4 py-2 tabular-nums">{e.roc_auc ?? '—'}</td><td className="px-4 py-2">{e.identity_disjoint == null ? t('unknown') : e.identity_disjoint ? t('yes') : t('no')}</td></tr>)}</tbody></table></div>
}

function ModelCard({ m, manage }: { m: ModelInfo; manage: boolean }) {
  const { t } = useT()
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const act = useMutation({
    mutationFn: () => (m.is_active ? deactivateModel(m.id) : activateModel(m.id)),
    onSuccess: () => { toast.success(m.is_active ? t('Model deactivated.') : t('Model activated.')); void qc.invalidateQueries({ queryKey: ['models'] }); void qc.invalidateQueries({ queryKey: ['dashboard'] }) },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const [confirmDelete, setConfirmDelete] = useState(false)
  const del = useMutation({
    mutationFn: () => deleteModel(m.id),
    onSuccess: () => { toast.success(t('Model deleted.')); setConfirmDelete(false); void qc.invalidateQueries({ queryKey: ['models'] }) },
    onError: (e) => toast.error(errorMessage(e)),
  })
  const ev = m.latest_evaluation
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3 p-5">
        <div><p className="font-medium">{m.name} <span className="font-normal text-muted">v{m.version}</span></p><p className="text-xs text-muted">{m.architecture}{m.trained_at ? ` · ${t('trained {when}', { when: formatDateTime(m.trained_at) })}` : ''}</p></div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={cn('rounded-md px-2 py-0.5', m.is_active ? 'bg-success/15 text-success' : 'bg-muted/15 text-muted')}>{m.is_active ? t('Active') : t('Inactive')}</span>
          <span className={cn('rounded-md px-2 py-0.5', m.is_trained ? 'bg-secondary/15 text-secondary' : 'bg-warning/15 text-warning')}>{m.is_trained ? t('Trained') : t('Untrained baseline')}</span>
          <span className={cn('rounded-md px-2 py-0.5', m.has_onnx ? 'bg-secondary/15 text-secondary' : 'bg-muted/15 text-muted')}>{m.has_onnx ? t('ONNX present') : t('No ONNX file')}</span>
          <span className="rounded-md bg-muted/15 px-2 py-0.5 text-muted" title={t('What the model expects as input')}>{m.input_crop === 'face' ? t('Input: face crop') : t('Input: full image')}</span>
        </div>
      </div>
      {ev ? <dl className="grid grid-cols-2 gap-px border-t border-border bg-border sm:grid-cols-4">
        {METRICS.map(([k, label]) => <div key={k} className="bg-card px-4 py-2.5"><dt className="text-xs text-muted">{/^[A-Z-]+$/.test(label) ? label : t(label)}</dt><dd className="text-sm font-medium tabular-nums">{ev[k] == null ? '—' : k === 'roc_auc' ? ev[k]!.toFixed(3) : formatPercent(ev[k])}</dd></div>)}
      </dl> : <p className="border-t border-border px-5 py-3 text-sm text-muted">{t('Not evaluated. No metrics are shown because none were measured.')}</p>}
      {m.blockers.length > 0 && <div className="border-t border-border bg-warning/5 px-5 py-3 text-xs text-warning"><p className="font-medium">{t('Cannot be activated yet')}</p><ul className="mt-1 list-disc space-y-0.5 pl-4">{m.blockers.map((b) => <li key={b}>{translateServer(b)}</li>)}</ul></div>}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border px-5 py-3">
        <button onClick={() => setOpen((o) => !o)} aria-expanded={open} className="flex cursor-pointer items-center gap-1 text-sm text-muted hover:text-fg"><ChevronDown className={cn('size-4 transition-transform', open && 'rotate-180')} />{t('Evaluation history')}</button>
        {manage && <div className="flex gap-2">
          {!m.is_active && <Button size="sm" variant="ghost" aria-label={t('Delete model {name} v{version}', { name: m.name, version: m.version })} onClick={() => setConfirmDelete(true)}><Trash2 className="size-4" /></Button>}
          <Button size="sm" variant={m.is_active ? 'outline' : 'default'} disabled={act.isPending || (!m.is_active && m.blockers.length > 0)} onClick={() => act.mutate()}>{m.is_active ? t('Deactivate') : t('Activate')}</Button>
        </div>}
      </div>
      {open && <div className="border-t border-border"><History id={m.id} /></div>}
      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} title={t('Delete {name} v{version}?', { name: m.name, version: m.version })}
        description={t('The ONNX file and its evaluations are removed. Verification results it produced keep their model label.')} busy={del.isPending} onConfirm={() => del.mutate()} />
    </Card>
  )
}

function FilePick({ label, accept, file, onChange, hint }: { label: string; accept: string; file: File | null; onChange: (f: File | null) => void; hint: string }) {
  const id = `file-${label.replace(/\W+/g, '-').toLowerCase()}`
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>
      <input id={id} type="file" accept={accept} onChange={(e) => onChange(e.target.files?.[0] ?? null)}
        className="block w-full cursor-pointer rounded-lg border border-border bg-bg text-sm text-muted file:mr-3 file:cursor-pointer file:border-0 file:bg-card-hover file:px-3 file:py-2 file:text-sm file:text-fg" />
      <p className="mt-1.5 text-xs text-muted">{file ? `${file.name} · ${(file.size / 1024).toFixed(0)} KB` : hint}</p>
    </div>
  )
}

function RegisterModel() {
  const { t } = useT()
  const qc = useQueryClient()
  const [f, setF] = useState({ name: '', version: '1.0.0', architecture: 'SmallCNN', description: '', input_crop: 'face' as 'full' | 'face' })
  const [files, setFiles] = useState<{ onnx: File | null; test_metrics: File | null; split_report: File | null }>({ onnx: null, test_metrics: null, split_report: null })
  const [progress, setProgress] = useState<number | null>(null)
  const [formKey, setFormKey] = useState(0)
  const reg = useMutation({
    mutationFn: () => registerModel({ ...f, onnx: files.onnx!, test_metrics: files.test_metrics!, split_report: files.split_report! }, setProgress),
    onSuccess: (m) => {
      toast.success(m.blockers.length ? t('Registered {name} v{version}. It cannot be activated yet; see the reasons on its card.', { name: m.name, version: m.version }) : t('Registered {name} v{version}. Review its metrics, then activate it.', { name: m.name, version: m.version }))
      setFiles({ onnx: null, test_metrics: null, split_report: null }); setFormKey((k) => k + 1)
      setF((s) => ({ ...s, name: '', description: '' }))
      void qc.invalidateQueries({ queryKey: ['models'] })
    },
    onError: (e) => toast.error(errorMessage(e)),
    onSettled: () => setProgress(null),
  })
  const ready = f.name.trim() && f.version.trim() && files.onnx && files.test_metrics && files.split_report
  function submit(e: FormEvent) { e.preventDefault(); if (ready) reg.mutate() }
  return (
    <Card>
      <CardHeader title={t('Register a trained model')} description={t('Upload the files a training run writes to ai/runs/<name>/. The model is checked with ONNX Runtime and is never activated automatically.')} />
      <form key={formKey} onSubmit={submit} className="space-y-4 p-5">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label={t('Name')} value={f.name} onChange={(e) => setF((s) => ({ ...s, name: e.target.value }))} maxLength={64} placeholder="smallcnn" required hint={t('Letters, digits, . _ -')} />
          <Field label={t('Version')} value={f.version} onChange={(e) => setF((s) => ({ ...s, version: e.target.value }))} maxLength={64} required />
          <Field label={t('Architecture')} value={f.architecture} onChange={(e) => setF((s) => ({ ...s, architecture: e.target.value }))} maxLength={120} />
          <div><label htmlFor="reg-crop" className="mb-1.5 block text-sm font-medium">{t('Trained on')}</label>
            <select id="reg-crop" value={f.input_crop} onChange={(e) => setF((s) => ({ ...s, input_crop: e.target.value as 'full' | 'face' }))}
              className="h-10 w-full rounded-lg border border-border bg-bg px-3 text-sm hover:border-muted/40"><option value="face">{t('Face crops')}</option><option value="full">{t('Full images')}</option></select>
            <p className="mt-1.5 text-xs text-muted">{t('Must match the dataset export you trained on.')}</p></div>
        </div>
        <Field label={t('Description (optional)')} value={f.description} onChange={(e) => setF((s) => ({ ...s, description: e.target.value }))} maxLength={2000} />
        <div className="grid gap-4 md:grid-cols-3">
          <FilePick label="model.onnx" accept=".onnx" file={files.onnx} onChange={(x) => setFiles((s) => ({ ...s, onnx: x }))} hint={t('Self-contained ONNX export')} />
          <FilePick label="test_metrics.json" accept=".json,application/json" file={files.test_metrics} onChange={(x) => setFiles((s) => ({ ...s, test_metrics: x }))} hint={t('Measured on the held-out test split')} />
          <FilePick label="split_report.json" accept=".json,application/json" file={files.split_report} onChange={(x) => setFiles((s) => ({ ...s, split_report: x }))} hint={t('Proves the split is identity-disjoint')} />
        </div>
        <div className="flex items-center justify-end gap-3">
          {progress != null && <span role="status" className="text-xs text-muted tabular-nums">{progress < 100 ? t('Uploading {pct}%', { pct: progress }) : t('Validating…')}</span>}
          <Button type="submit" disabled={!ready || reg.isPending}><Upload className="size-4" />{reg.isPending ? t('Registering…') : t('Register model')}</Button>
        </div>
      </form>
    </Card>
  )
}

function TrainingGuide() {
  const { t } = useT()
  const [datasetId, setDatasetId] = useState('')
  const [p, setP] = useState({ epochs: 20, batch: 32, lr: 0.001, size: 112 })
  const [crop, setCrop] = useState<'full' | 'face'>('face')
  const [copied, setCopied] = useState(false)
  const datasets = useQuery({ queryKey: ['datasets'], queryFn: listDatasets, retry: false })
  const validation = useQuery({ queryKey: ['dataset-validation', datasetId], queryFn: () => getValidation(datasetId), enabled: !!datasetId, retry: false })
  const config = useMemo(() => JSON.stringify({ manifest: 'data/manifest.csv', root: 'data', out_dir: 'runs/exp1', epochs: p.epochs, batch_size: p.batch, lr: p.lr, image_size: p.size, seed: 42, device: 'auto' }, null, 2), [p])
  const exportName = crop === 'face' ? t('Export face crops') : t('Export ZIP')
  const inputName = crop === 'face' ? t('face crop') : t('full image')
  const commands = `# 1. ${t('On the dataset\'s page choose "{button}" and unzip it into ai/data/', { button: exportName })}\n# 2. ${t('Save this as ai/config.json:')}\n${config}\n\n# 3. ${t('Train, then export (needs: pip install -r ai/requirements.txt)')}\ncd ai\npython -m faceguard_ai.train --config config.json\npython -m faceguard_ai.export runs/exp1/best.pt runs/exp1/model.onnx\n\n# 4. ${t('Register the run: upload model.onnx, test_metrics.json and split_report.json with the form above')}\n#    ${t('(input: {input}), or from the command line:', { input: inputName })}\ncd ../backend\npython scripts/register_model.py --run-dir ../ai/runs/exp1 --name smallcnn --version 1.0.0 --crop ${crop}`
  return (
    <Card>
      <CardHeader title={t('Training')} description={t('Training is not started from this page.')} />
      <div className="space-y-4 p-5">
        <div className="flex gap-2.5 rounded-lg border border-border bg-bg p-3 text-xs text-muted"><Info className="mt-0.5 size-4 shrink-0" /><p>{t('Training needs PyTorch and your own labelled data, and can take hours, so it runs from the command line ({dir}). This server records no training jobs and shows no progress, because none run here. Prepare a command for a dataset below. Face crops are recommended: the model then sees the face exactly as the verification pipeline crops it. After training, register the run with the form above; activation is still refused unless the evidence is sufficient.', { dir: 'ai/' })}</p></div>
        <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <div><Select label={t('Model input')} value={crop} onChange={(e) => setCrop(e.target.value as 'full' | 'face')}><option value="face">{t('Face crops (recommended)')}</option><option value="full">{t('Full images')}</option></Select></div>
          <div className="sm:col-span-2 lg:col-span-1"><Select label={t('Dataset')} value={datasetId} onChange={(e) => setDatasetId(e.target.value)} disabled={!datasets.data?.length}><option value="">{datasets.data?.length ? t('Choose…') : t('No datasets')}</option>{datasets.data?.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></div>
          {([['epochs', 'Epochs', 1, 500, 1], ['batch', 'Batch size', 1, 512, 1], ['lr', 'Learning rate', 0.00001, 1, 0.0001], ['size', 'Image size (px)', 32, 512, 8]] as const).map(([k, label, min, max, step]) => (
            <div key={k}><label className="mb-1 block text-xs text-muted" htmlFor={`tr-${k}`}>{t(label)}</label><input id={`tr-${k}`} type="number" min={min} max={max} step={step} value={p[k]} onChange={(e) => setP((s) => ({ ...s, [k]: Number(e.target.value) }))} className="h-9 w-full rounded-lg border border-border bg-bg px-2.5 text-sm" /></div>))}
        </div>
        {validation.data && (validation.data.ready ? <p className="flex items-center gap-2 text-sm text-success"><Check className="size-4" />{t('This dataset passes the readiness checks.')}</p>
          : <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning"><p className="font-medium">{t('Not ready for training')}</p><ul className="mt-1 list-disc pl-4">{validation.data.problems.map((x) => <li key={x}>{translateServer(x)}</li>)}</ul></div>)}
        <div className="relative"><pre className="max-h-72 overflow-auto rounded-lg border border-border bg-bg p-4 text-xs leading-relaxed">{commands}</pre>
          <Button variant="outline" size="sm" className="absolute right-2 top-2" onClick={async () => { try { await navigator.clipboard.writeText(commands); setCopied(true); setTimeout(() => setCopied(false), 1500) } catch { toast.error(t('Copy failed. Select the text manually.')) } }}>{copied ? <Check className="size-4" /> : <Copy className="size-4" />}{copied ? t('Copied') : t('Copy')}</Button></div>
      </div>
    </Card>
  )
}

export default function ModelsPage() {
  const { t } = useT()
  const { user } = useAuth()
  const manage = user?.role === 'administrator' || user?.role === 'researcher'
  const models = useQuery({ queryKey: ['models'], queryFn: listModels, retry: false })
  const active = models.data?.find((m) => m.is_active)
  return (
    <div className="space-y-6">
      <PageHeader title={t('Models')} description={t('Anti-spoofing models and the evidence behind them. A model is activated only with a real evaluation.')} />
      {models.data && (active
        ? <div className="flex gap-2.5 rounded-xl border border-success/30 bg-success/10 p-4 text-xs leading-relaxed text-success"><Check className="mt-0.5 size-4 shrink-0" />
            <p><span className="font-medium">{t('{name} v{version} decides liveness.', { name: active.name, version: active.version })}</span> {t('Every image, video and challenge with exactly one face is scored by it. Scores close to its threshold, or on images that fail the quality checks, stay Uncertain.')}</p></div>
        : <div className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-xs leading-relaxed text-warning"><p className="font-medium">{t('No model is active.')}</p>
            <p className="mt-1">{t('Verification results stay Uncertain until a trained model with a sufficient, identity-disjoint evaluation is registered and activated.')}</p></div>)}
      {models.isError && <ErrorState title={t('Models unavailable')} message={errorMessage(models.error)} onRetry={() => void models.refetch()} />}
      {models.isLoading ? <Skeleton className="h-40" /> : models.data && models.data.length > 0
        ? <div className="space-y-4">{models.data.map((m) => <ModelCard key={m.id} m={m} manage={manage} />)}</div>
        : <Card><EmptyState icon={Boxes} title={t('No models registered')} hint={t('No model has been trained and registered. Trained models appear here with their measured metrics.')} /></Card>}
      {manage && <RegisterModel />}
      {manage && <TrainingGuide />}
    </div>
  )
}
