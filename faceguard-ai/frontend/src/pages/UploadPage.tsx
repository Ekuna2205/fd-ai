import { useQuery } from '@tanstack/react-query'
import { FileVideo, ImageIcon, Loader2, UploadCloud, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from 'react'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { ErrorState } from '@/components/ui/state'
import { ResultPanel } from '@/components/verify/ResultPanel'
import { useAuth } from '@/hooks/useAuth'
import { errorMessage } from '@/services/api'
import { getCapabilities, uploadMedia } from '@/services/face'
import type { VerificationResult } from '@/types/face'
import { cn } from '@/utils/cn'
import { canVerify } from '@/utils/roles'
import { useT } from '@/i18n'

const ext = (name: string) => name.slice(name.lastIndexOf('.')).toLowerCase()

export default function UploadPage() {
  const { t } = useT()
  const { user } = useAuth()
  const allowed = canVerify(user?.role)
  const caps = useQuery({ queryKey: ['face-capabilities'], queryFn: getCapabilities, retry: false, enabled: allowed })
  const limits = caps.data?.limits
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [consent, setConsent] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [failure, setFailure] = useState<string | null>(null)

  const kind = file ? (limits?.video_types.includes(ext(file.name)) ? 'video' : 'image') : null
  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file])
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl) }, [previewUrl])

  const choose = useCallback((f: File | undefined) => {
    setResult(null); setFailure(null); setProgress(null)
    if (!f || !limits) return
    const e = ext(f.name)
    const isImage = limits.image_types.includes(e), isVideo = limits.video_types.includes(e)
    if (!isImage && !isVideo) { setFile(null); setProblem(t('Unsupported file type. Use {types}.', { types: [...limits.image_types, ...limits.video_types].join(', ') })); return }
    const maxMb = isImage ? limits.max_image_mb : limits.max_video_mb
    if (f.size > maxMb * 1024 * 1024) { setFile(null); setProblem(isImage ? t('File is too large. The limit is {mb} MB for images.', { mb: maxMb }) : t('File is too large. The limit is {mb} MB for videos.', { mb: maxMb })); return }
    if (f.size === 0) { setFile(null); setProblem(t('The file is empty.')); return }
    setProblem(null); setFile(f)
  }, [limits])

  const onDrop = (e: DragEvent) => { e.preventDefault(); setDragging(false); choose(e.dataTransfer.files[0]) }
  const reset = () => { setFile(null); setResult(null); setFailure(null); setProgress(null); setProblem(null); if (inputRef.current) inputRef.current.value = '' }

  async function analyse() {
    if (!file || !kind) return
    setBusy(true); setFailure(null); setResult(null); setProgress(0)
    try {
      setResult(await uploadMedia(file, kind, setProgress))
      toast.success(t('Analysis complete.'))
    } catch (e) { setFailure(errorMessage(e)) } finally { setBusy(false) }
  }

  if (!allowed) {
    return <div className="space-y-6"><h1 className="text-2xl font-semibold tracking-tight">{t('Upload')}</h1>
      <div role="alert" className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">{t('Your role is read-only. Ask an administrator for Operator access to upload media.')}</div></div>
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('Upload')}</h1>
        <p className="mt-1 text-sm text-muted">{t('Analyse an image or a short video. Files are processed and discarded; only the result is stored.')}</p>
      </div>
      {caps.isError && <ErrorState title={t('Upload limits unavailable')} message={errorMessage(caps.error)} onRetry={() => void caps.refetch()} />}

      {!file ? (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
          onClick={() => inputRef.current?.click()} role="button" tabIndex={0} aria-label={t('Choose a file to analyse')}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && inputRef.current?.click()}
          className={cn('flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-14 text-center transition-colors',
            dragging ? 'border-primary bg-primary/5' : 'border-border hover:border-muted/50')}>
          <UploadCloud className="size-9 text-primary" />
          <p className="text-sm font-medium">{t('Drag a file here, or click to browse')}</p>
          <p className="text-xs text-muted">{limits ? t('{imageTypes} up to {imageMb} MB · {videoTypes} up to {videoMb} MB and {seconds} s', { imageTypes: limits.image_types.join(', '), imageMb: limits.max_image_mb, videoTypes: limits.video_types.join(', '), videoMb: limits.max_video_mb, seconds: limits.max_video_seconds }) : t('Loading limits…')}</p>
          <input ref={inputRef} type="file" hidden disabled={!limits} accept={limits ? [...limits.image_types, ...limits.video_types].join(',') : undefined} onChange={(e) => choose(e.target.files?.[0])} />
        </div>
      ) : (
        <Card className="overflow-hidden">
          <div className="flex items-center gap-3 border-b border-border px-4 py-3">
            {kind === 'video' ? <FileVideo className="size-5 text-primary" /> : <ImageIcon className="size-5 text-primary" />}
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{file.name}</p><p className="text-xs text-muted">{(file.size / 1048576).toFixed(2)} MB</p></div>
            <Button variant="ghost" size="icon" onClick={reset} disabled={busy} aria-label={t('Remove file')}><X className="size-4" /></Button>
          </div>
          <div className="grid place-items-center bg-black">
            {kind === 'video'
              ? <video src={previewUrl ?? undefined} controls muted className="max-h-96 w-full" />
              : <img src={previewUrl ?? undefined} alt={t('Selected file preview')} className="max-h-96 object-contain" />}
          </div>
          <div className="space-y-4 p-4">
            <label className="flex cursor-pointer items-start gap-2.5 text-sm">
              <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} disabled={busy} className="mt-0.5 size-4 accent-[#22D3EE]" />
              <span>{t('I confirm I have the right to analyse this media and consent to its processing. It will not be stored.')}</span>
            </label>
            {busy && (
              <div role="status" aria-live="polite">
                <div className="h-1.5 overflow-hidden rounded-full bg-border"><div className="h-full bg-primary transition-all" style={{ width: `${progress ?? 0}%` }} /></div>
                <p className="mt-2 flex items-center gap-2 text-xs text-muted"><Loader2 className="size-3 animate-spin" />{progress != null && progress < 100 ? t('Uploading {pct}%', { pct: progress }) : t('Analysing on the server…')}</p>
              </div>
            )}
            <Button onClick={analyse} disabled={!consent || busy}>{busy ? t('Working…') : t('Analyse')}</Button>
          </div>
        </Card>
      )}

      {problem && <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-3 py-2.5 text-sm text-danger">{problem}</div>}
      {failure && <ErrorState title={t('The file could not be analysed')} message={failure} />}
      {result && <><ResultPanel result={result} linkToDetail /><Button variant="outline" onClick={reset}>{t('Analyse another file')}</Button></>}
    </div>
  )
}
