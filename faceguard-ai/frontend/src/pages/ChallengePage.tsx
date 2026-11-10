import { Camera, CameraOff, CheckCircle2, CircleDashed, Info, Loader2, RotateCcw, Square, XCircle } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { StatusBadge } from '@/components/StatusBadge'
import type { VerificationStatus } from '@/types/dashboard'
import { PageHeader } from '@/components/PageHeader'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { ErrorState } from '@/components/ui/state'
import { ConsentCard } from '@/components/verify/ConsentCard'
import { useAuth } from '@/hooks/useAuth'
import { useCamera } from '@/hooks/useCamera'
import { errorMessage } from '@/services/api'
import { newChallenge, submitChallenge } from '@/services/challenge'
import type { Challenge, ChallengeResult } from '@/types/challenge'
import { cn } from '@/utils/cn'
import { canVerify } from '@/utils/roles'
import { translateServer, useT } from '@/i18n'

type Phase = 'idle' | 'ready' | 'recording' | 'uploading' | 'done'
const MIME = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm', 'video/mp4']
const pickMime = () => (typeof MediaRecorder === 'undefined' ? undefined : MIME.find((m) => MediaRecorder.isTypeSupported(m)))
const STATE_ICON = { PASSED: CheckCircle2, FAILED: XCircle, TIMED_OUT: XCircle } as const
const OUTCOME: Record<string, string> = { PASSED: 'Challenge passed', FAILED: 'Challenge failed', TIMED_OUT: 'Challenge timed out' }
const STEP_STATE: Record<string, string> = { PASSED: 'passed', FAILED: 'failed', TIMED_OUT: 'timed out', PENDING: 'pending', ACTIVE: 'in progress' }

export default function ChallengePage() {
  const { t } = useT()
  const { user } = useAuth()
  const allowed = canVerify(user?.role)
  const cam = useCamera()
  const [consented, setConsented] = useState(false)
  const [challenge, setChallenge] = useState<Challenge | null>(null)
  const [phase, setPhase] = useState<Phase>('idle')
  const [step, setStep] = useState({ index: 0, remaining: 0 })
  const [expiresIn, setExpiresIn] = useState<number | null>(null)
  const [result, setResult] = useState<ChallengeResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const timer = useRef<number | undefined>(undefined)
  const cancelled = useRef(false)
  const active = cam.status === 'active'

  const clearTimer = () => window.clearInterval(timer.current)
  useEffect(() => () => { cancelled.current = true; clearTimer(); if (recorder.current?.state === 'recording') recorder.current.stop() }, [])

  // Count down the lifetime of an issued (not yet used) challenge.
  useEffect(() => {
    if (phase !== 'ready' || !challenge) return
    const tick = () => {
      const left = Math.floor(challenge.expires_at - Date.now() / 1000)
      setExpiresIn(left)
      if (left <= 0) { setPhase('idle'); setChallenge(null); setError(t('The challenge expired before it was started. Request a new one.')) }
    }
    tick(); const timer = window.setInterval(tick, 500)
    return () => window.clearInterval(timer)
  }, [phase, challenge])

  const request = useCallback(async () => {
    setError(null); setResult(null)
    try { setChallenge(await newChallenge()); setPhase('ready') } catch (e) { setError(errorMessage(e)) }
  }, [])

  const finish = useCallback(async (c: Challenge, chunks: Blob[], type: string) => {
    if (cancelled.current) return
    setPhase('uploading'); setProgress(0)
    const blob = new Blob(chunks, { type })
    try {
      setResult(await submitChallenge(c.token, blob, `challenge${type.includes('mp4') ? '.mp4' : '.webm'}`, setProgress)); setPhase('done')
    } catch (e) {
      // The token is single-use, so even a failed upload needs a fresh challenge.
      setError(errorMessage(e)); setChallenge(null); setPhase('idle')
    }
  }, [])

  function start() {
    const video = cam.videoRef.current
    const stream = video?.srcObject
    const mimeType = pickMime()
    if (!challenge || !(stream instanceof MediaStream) || !mimeType) { setError(t('This browser cannot record video (MediaRecorder is unavailable).')); return }
    const chunks: Blob[] = []
    const rec = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 1_500_000 })
    rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data) }
    rec.onstop = () => { clearTimer(); void finish(challenge, chunks, rec.mimeType || mimeType) }
    recorder.current = rec
    const total = challenge.steps.length * challenge.step_timeout_seconds
    const t0 = performance.now()
    rec.start(250)
    setPhase('recording'); setStep({ index: 0, remaining: challenge.step_timeout_seconds })
    timer.current = window.setInterval(() => {
      const elapsed = (performance.now() - t0) / 1000
      if (elapsed >= total) { rec.state === 'recording' && rec.stop(); return }
      const index = Math.floor(elapsed / challenge.step_timeout_seconds)
      setStep({ index, remaining: Math.ceil(challenge.step_timeout_seconds - (elapsed - index * challenge.step_timeout_seconds)) })
    }, 100)
  }

  if (!allowed) return <div className="space-y-6"><PageHeader title={t('Liveness challenge')} /><div role="alert" className="rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">{t('Your role is read-only. Ask an administrator for Operator access.')}</div></div>

  return (
    <div className="space-y-6">
      <PageHeader title={t('Liveness challenge')} description={t('Follow a randomly chosen sequence of movements. The server, not your browser, evaluates the recording.')} />
      <div role="note" className="flex gap-2.5 rounded-xl border border-warning/30 bg-warning/10 p-4 text-xs leading-relaxed text-warning"><Info className="mt-0.5 size-4 shrink-0" />
        <p><strong className="font-medium">{t('A passed challenge is supporting evidence only.')}</strong> {t('Movements can be imitated by recordings and manipulated video, so passing alone never marks a person as real. A Real result also needs the active anti-spoofing model to agree.')}</p></div>

      {!consented ? <ConsentCard action={t('Continue to camera')} onConsent={() => setConsented(true)} /> : (
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Card className="overflow-hidden">
              <div className="relative w-full overflow-hidden bg-black" style={{ aspectRatio: cam.aspect }}>
                <div className="absolute inset-0 -scale-x-100"><video ref={cam.videoRef} playsInline muted autoPlay className="size-full object-cover" /></div>
                {!active && <div className="absolute inset-0 grid place-items-center text-muted">{cam.status === 'starting' ? <Loader2 className="size-6 animate-spin text-primary" /> : <div className="space-y-2 text-center"><CameraOff className="mx-auto size-8" /><p className="text-sm">{t('Camera is off')}</p></div>}</div>}
                {phase === 'recording' && challenge && <>
                  <div className="absolute left-3 top-3 flex items-center gap-2 rounded-full bg-bg/80 px-3 py-1 text-xs backdrop-blur"><span className="size-2 animate-pulse rounded-full bg-danger" />{t('Recording')}</div>
                  <div className="absolute inset-x-3 bottom-3 rounded-lg bg-bg/85 px-4 py-3 text-center backdrop-blur" role="status" aria-live="assertive">
                    <p className="text-xs text-muted">{t('Step {n} of {total}', { n: step.index + 1, total: challenge.steps.length })}</p><p className="text-lg font-semibold">{translateServer(challenge.steps[step.index]?.instruction)}</p><p className="text-sm tabular-nums text-muted">{step.remaining}s</p></div></>}
              </div>
              <div className="flex flex-wrap items-center gap-2 p-4">
                {!active ? <Button onClick={() => void cam.start(cam.deviceId)} disabled={cam.status === 'starting'}><Camera className="size-4" />{t('Start camera')}</Button>
                  : phase === 'recording' ? <Button variant="danger" onClick={() => recorder.current?.state === 'recording' && recorder.current.stop()}><Square className="size-4" />{t('Finish early')}</Button>
                  : <>
                    {phase !== 'ready' && phase !== 'uploading' && <Button onClick={() => void request()}>{phase === 'done' ? <RotateCcw className="size-4" /> : null}{phase === 'done' ? t('Try again with a new challenge') : t('Get a challenge')}</Button>}
                    {phase === 'ready' && <Button onClick={start}>{t('Start recording')}</Button>}
                    <Button variant="outline" onClick={cam.stop} disabled={phase === 'uploading'}><CameraOff className="size-4" />{t('Stop camera')}</Button></>}
                {phase === 'ready' && expiresIn != null && <span className="ml-auto text-xs text-muted tabular-nums">{t('Expires in {s}s', { s: expiresIn })}</span>}
              </div>
              {phase === 'uploading' && <p role="status" className="flex items-center gap-2 border-t border-border px-4 py-3 text-sm text-muted"><Loader2 className="size-4 animate-spin" />{progress != null && progress < 100 ? t('Uploading {pct}%', { pct: progress }) : t('Evaluating on the server…')}</p>}
            </Card>
            {cam.error && <ErrorState title={t('Camera unavailable')} message={cam.error} onRetry={() => void cam.start(cam.deviceId)} />}
            {error && <ErrorState title={t('Challenge problem')} message={error} />}
          </div>

          <div className="space-y-4">
            <Card><CardHeader title={t('Your challenge')} description={challenge ? t('{s}s per step, in this order', { s: challenge.step_timeout_seconds }) : t('Request one to begin')} />
              {challenge ? <ol className="divide-y divide-border">{challenge.steps.map((s, i) => {
                const outcome = result?.progress.steps[i]
                const Icon = outcome ? (outcome.state === 'PASSED' ? CheckCircle2 : XCircle) : CircleDashed
                return <li key={i} className={cn('flex items-center gap-3 px-5 py-3 text-sm', phase === 'recording' && step.index === i && 'bg-primary/5')}>
                  <Icon className={cn('size-4 shrink-0', outcome ? (outcome.state === 'PASSED' ? 'text-success' : 'text-danger') : 'text-muted')} aria-hidden />
                  <span className="flex-1">{translateServer(s.instruction)}</span>{outcome && <span className="text-xs text-muted">{t(STEP_STATE[outcome.state] ?? outcome.state)}</span>}</li>
              })}</ol> : <p className="px-5 py-6 text-sm text-muted">{t('Start the camera, then choose “Get a challenge”.')}</p>}
            </Card>
            {result && (() => { const Icon = STATE_ICON[result.outcome as keyof typeof STATE_ICON] ?? XCircle; return (
              <Card><CardHeader title={t('Result')} /><div className="space-y-3 p-5 text-sm">
                <p className={cn('flex items-center gap-2 font-medium', result.outcome === 'PASSED' ? 'text-success' : 'text-warning')}><Icon className="size-4" />{t(OUTCOME[result.outcome] ?? 'Challenge finished')}</p>
                <p className="text-muted">{translateServer(result.note)}</p>
                <dl className="space-y-1 text-xs"><div className="flex justify-between"><dt className="text-muted">{t('Face detected')}</dt><dd>{result.assessment.face_detected ? t('yes') : t('no')}</dd></div>
                  <div className="flex justify-between"><dt className="text-muted">{t('Anti-spoofing model')}</dt><dd className={result.assessment.ai_classification_available ? '' : 'text-warning'}>{result.assessment.ai_classification_available ? t('scored the recording') : t('not available')}</dd></div>
                  <div className="flex justify-between"><dt className="text-muted">{t('Overall result')}</dt><dd><StatusBadge status={result.status as VerificationStatus} /></dd></div></dl>
                <p className="rounded-lg bg-bg p-3 text-xs">{translateServer(result.assessment.statement)}</p>
                <Link to={`/verifications/${result.verification_id}`} className="text-primary hover:underline">{t('Open the stored record')}</Link></div></Card>) })()}
          </div>
        </div>)}
    </div>
  )
}
