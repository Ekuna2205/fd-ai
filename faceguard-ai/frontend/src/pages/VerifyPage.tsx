import { useQuery } from '@tanstack/react-query'
import { Camera, CameraOff, Loader2, RefreshCw, ScanFace, SwitchCamera } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { ConsentCard } from '@/components/verify/ConsentCard'
import { FaceOverlay } from '@/components/verify/FaceOverlay'
import { QualityList } from '@/components/verify/QualityList'
import { ResultPanel } from '@/components/verify/ResultPanel'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { ErrorState } from '@/components/ui/state'
import { frameToBlob, useCamera } from '@/hooks/useCamera'
import { useAuth } from '@/hooks/useAuth'
import { useLiveDetection } from '@/hooks/useLiveDetection'
import { errorMessage } from '@/services/api'
import { getCapabilities, verifyFrame } from '@/services/face'
import type { VerificationResult } from '@/types/face'
import { cn } from '@/utils/cn'
import { canVerify } from '@/utils/roles'
import { translateServer, useT } from '@/i18n'

export default function VerifyPage() {
  const { t } = useT()
  const { user } = useAuth()
  const allowed = canVerify(user?.role)
  const [consented, setConsented] = useState(false)
  const [result, setResult] = useState<VerificationResult | null>(null)
  const [verifying, setVerifying] = useState(false)
  const cam = useCamera()
  const active = cam.status === 'active'
  const live = useLiveDetection(cam.videoRef, active)
  const caps = useQuery({ queryKey: ['face-capabilities'], queryFn: getCapabilities, retry: false, enabled: allowed })
  const det = live.detection
  const oneFace = det?.face_count === 1

  async function capture() {
    const video = cam.videoRef.current
    if (!video) return
    setVerifying(true)
    try {
      const frame = await frameToBlob(video, 960, 0.85) // a fresh, higher-resolution frame, not the preview frame
      const res = await verifyFrame(frame)
      setResult(res)
      toast.success(t('Verification recorded.'))
    } catch (e) {
      toast.error(errorMessage(e))
    } finally { setVerifying(false) }
  }

  const guidance = !active ? null : det ? translateServer(det.guidance[0]) : t('Starting detection…')
  const tone = !det ? 'border-border' : det.face_count > 1 ? 'border-danger/50' : oneFace && det.quality?.ready ? 'border-success/50' : 'border-warning/50'

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('Live verification')}</h1>
        <p className="mt-1 text-sm text-muted">{t('Detect a face, check capture quality, and record a verification from your camera.')}</p>
      </div>

      {!allowed && <div role="alert" className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">{t('Your role is read-only. Ask an administrator for Operator access to run verifications.')}</div>}

      {allowed && !consented && <ConsentCard action={t('Continue to camera')} onConsent={() => setConsented(true)} />}

      {allowed && consented && (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Card className="overflow-hidden">
              <div className={cn('relative w-full overflow-hidden bg-black transition-colors', active && 'border-b-2', tone)} style={{ aspectRatio: cam.aspect }}>
                <div className="absolute inset-0 -scale-x-100">{/* mirrored like a mirror; overlay is mirrored with it */}
                  <video ref={cam.videoRef} playsInline muted autoPlay className="size-full object-cover" />
                  <FaceOverlay detection={det} />
                </div>
                {active && !oneFace && !det?.face_count && (
                  <svg className="pointer-events-none absolute inset-0 size-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden>
                    <ellipse cx="50" cy="50" rx="20" ry="36" fill="none" stroke="rgba(248,250,252,0.35)" strokeWidth="0.4" strokeDasharray="2 1.5" vectorEffect="non-scaling-stroke" />
                  </svg>
                )}
                {!active && (
                  <div className="absolute inset-0 grid place-items-center p-6 text-center">
                    {cam.status === 'starting' ? <Loader2 className="size-6 animate-spin text-primary" />
                      : <div className="space-y-2 text-muted"><CameraOff className="mx-auto size-8" /><p className="text-sm">{t('Camera is off')}</p></div>}
                  </div>
                )}
                {guidance && (
                  <div className="absolute inset-x-3 bottom-3 rounded-lg bg-bg/80 px-3 py-2 text-center text-sm backdrop-blur" role="status" aria-live="polite">{guidance}</div>
                )}
              </div>
              <div className="flex flex-wrap items-center gap-2 p-4">
                {!active
                  ? <Button onClick={() => void cam.start(cam.deviceId)} disabled={cam.status === 'starting'}><Camera className="size-4" />{cam.status === 'starting' ? t('Starting…') : t('Start camera')}</Button>
                  : <Button variant="outline" onClick={cam.stop}><CameraOff className="size-4" />{t('Stop camera')}</Button>}
                {active && cam.devices.length > 1 && <Button variant="outline" onClick={cam.switchCamera}><SwitchCamera className="size-4" />{t('Switch camera')}</Button>}
                <Button className="ml-auto" onClick={capture} disabled={!active || !oneFace || verifying}>
                  {verifying ? <Loader2 className="size-4 animate-spin" /> : <ScanFace className="size-4" />}{verifying ? t('Analysing…') : t('Capture & verify')}
                </Button>
              </div>
              {active && oneFace && !det?.quality?.ready && <p className="border-t border-border px-4 py-2.5 text-xs text-warning">{t('Quality issues are listed on the right. You can still capture, but the result may be less reliable.')}</p>}
            </Card>
            {cam.error && <ErrorState title={t('Camera unavailable')} message={cam.error} onRetry={() => void cam.start(cam.deviceId)} />}
            {live.halted && <ErrorState title={t('Live detection stopped')} message={live.error ?? t('Repeated errors from the server.')} onRetry={live.restart} />}
            {result && <ResultPanel result={result} linkToDetail />}
          </div>

          <div className="space-y-4">
            <Card>
              <CardHeader title={t('Capture quality')} description={t('Updated about four times per second')} />
              <QualityList quality={det?.quality ?? null} />
            </Card>
            <Card>
              <CardHeader title={t('Status')} />
              <dl className="divide-y divide-border text-sm">
                {([
                  ['Camera', cam.status === 'active' ? t('Active') : cam.status === 'starting' ? t('Starting') : cam.status === 'error' ? t('Error') : t('Off')],
                  ['Faces in view', det ? String(det.face_count) : '—'],
                  ['Detection time', live.latencyMs != null ? t('{ms} ms round trip', { ms: live.latencyMs }) : '—'],
                  ['Detector', caps.data ? `${caps.data.detector.name}${caps.data.detector.landmarks ? '' : ` ${t('(no landmarks)')}`}` : caps.isError ? t('Unavailable') : '…'],
                  ['Liveness model', caps.data ? (caps.data.liveness.model ?? t('None active')) : '…'],
                ] as const).map(([k, v]) => <div key={k} className="flex justify-between gap-3 px-5 py-2.5"><dt className="text-muted">{t(k)}</dt><dd className="text-right">{v}</dd></div>)}
              </dl>
            </Card>
            {caps.data && !caps.data.liveness.available && (
              <div className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-xs leading-relaxed text-warning">
                <p className="font-medium">{t('Liveness model not available')}</p>
                <p className="mt-1">{translateServer(caps.data.liveness.reason)} {t('Verifications will be recorded as Uncertain until a trained model is active.')}</p>
              </div>
            )}
            {live.error && !live.halted && <p className="flex items-center gap-2 text-xs text-danger"><RefreshCw className="size-3 animate-spin" />{t('Retrying: {error}', { error: live.error })}</p>}
          </div>
        </div>
      )}
    </div>
  )
}
