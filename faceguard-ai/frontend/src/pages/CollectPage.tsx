/**
 * Public data-collection page (collect.ekyc.mn-style). No account: the link token is the credential.
 *
 * label -> "before you start" -> camera inside an oval:
 *   face in frame -> turn right / turn left (random order) -> move closer -> hold still -> colour flashes
 * The whole sequence is recorded (MediaRecorder) and uploaded once; the server keeps a few single-face frames as
 * labelled dataset images. Live guidance comes from /collect/{token}/frame (~4 fps), nothing of which is stored.
 */
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ClipboardList, Loader2, ScanFace, ShieldAlert, UserCheck } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router-dom'
import { LanguageSwitch } from '@/components/LanguageSwitch'
import { Logo } from '@/components/Logo'
import { frameToBlob, useCamera } from '@/hooks/useCamera'
import { hasSavedLang, translateServer, useT } from '@/i18n'
import { spoofLabel } from '@/i18n/labels'
import { errorMessage } from '@/services/api'
import { getCollectInfo, sendCollectFrame, submitCollect } from '@/services/collect'
import type { CollectFrame, CollectLabel, CollectResult } from '@/types/collect'
import { cn } from '@/utils/cn'

type Stage = 'label' | 'intro' | 'camera' | 'flash' | 'upload' | 'result'
type Step = 'POSITION' | 'TURN_RIGHT' | 'TURN_LEFT' | 'CLOSER' | 'STILL'

const STEP_TEXT: Record<Step, string> = {
  POSITION: 'Place your face inside the frame',
  TURN_RIGHT: 'Slowly turn your head to the right',
  TURN_LEFT: 'Slowly turn your head to the left',
  CLOSER: 'Move a little closer to the camera',
  STILL: 'Keep your face still',
}
const FLASH = ['#00F5FF', '#FF1A1A', '#FFF200', '#1AFF3C'] // screen colours reflected by a real face
const FLASH_MS = 750
const MAX_RECORD_MS = 24_000 // server limit is 30 s
// 640x480 at ~0.7 Mbit/s: a 20 s recording is ~2 MB and decodes quickly even on a free 0.1-CPU / 512 MB server
const COLLECT_SIZE = { width: 640, height: 480 }
const TURN = 0.3 // |yaw| that counts as turned (same as the server challenge engine)
const MIME = ['video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm', 'video/mp4']
const pickMime = () => (typeof MediaRecorder === 'undefined' ? undefined : MIME.find((m) => MediaRecorder.isTypeSupported(m)))
const clamp01 = (v: number) => Math.max(0, Math.min(1, v))

function participantId(): string {
  const KEY = 'faceguard.participant'
  try {
    const saved = localStorage.getItem(KEY)
    if (saved && /^[a-f0-9]{16}$/.test(saved)) return saved
  } catch { /* storage unavailable */ }
  const id = Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, '0')).join('')
  try { localStorage.setItem(KEY, id) } catch { /* in-memory for this visit */ }
  return id
}

export default function CollectPage() {
  const { token = '' } = useParams()
  return <CollectFlow token={token} />
}

/** The whole participant flow. `embedded`: shown inside the signed-in app layout (no own header). */
export function CollectFlow({ token, embedded = false }: { token: string; embedded?: boolean }) {
  const { t, setLang } = useT()
  const info = useQuery({ queryKey: ['collect', token], queryFn: () => getCollectInfo(token), retry: false })
  const [stage, setStage] = useState<Stage>('label')
  const [label, setLabel] = useState<CollectLabel | null>(null)
  const [attack, setAttack] = useState<string | null>(null)
  const [consent, setConsent] = useState(false)
  const [result, setResult] = useState<CollectResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { if (!embedded && !hasSavedLang()) setLang('mn', false) }, [embedded, setLang]) // participants are addressed in Mongolian first

  const ready = label === 'REAL' || (label === 'FAKE' && !!attack)
  const home = () => { setStage('label'); setResult(null); setError(null) }

  return (
    <div className={embedded ? '' : 'min-h-dvh bg-bg text-fg'}>
      {!embedded && (
        <header className="mx-auto flex max-w-md items-center justify-between px-4 py-3">
          <Logo compact /><LanguageSwitch />
        </header>
      )}
      <main className={embedded ? 'mx-auto max-w-md pb-6' : 'mx-auto max-w-md px-4 pb-10'}>
        {info.isLoading && <Centered><Loader2 className="size-6 animate-spin text-primary" /></Centered>}
        {info.isError && (
          <Centered>
            <ShieldAlert className="size-8 text-danger" />
            <p className="mt-3 font-medium">{t('This collection link is not valid or has been turned off.')}</p>
            <p className="mt-1 text-sm text-muted">{t('Ask the person who sent it for a new link.')}</p>
          </Centered>
        )}

        {info.data && stage === 'label' && (
          <section aria-labelledby="label-title">
            <h1 id="label-title" className="mt-2 text-xl font-semibold">{t('Label options')}</h1>
            <p className="mt-1 text-sm text-muted">{info.data.name}{info.data.description ? ` · ${info.data.description}` : ''}</p>
            <div className="mt-5 grid gap-3" role="radiogroup" aria-label={t('Label options')}>
              <LabelCard selected={label === 'REAL'} onSelect={() => { setLabel('REAL'); setAttack(null) }} icon={UserCheck}
                title={t('Genuine')} text={t('Choose me')} tone="success" />
              <LabelCard selected={label === 'FAKE'} onSelect={() => setLabel('FAKE')} icon={ScanFace}
                title={t('Fake')} text={t('Try to deceive the camera with a photo or a video')} tone="danger" />
            </div>
            {label === 'FAKE' && (
              <fieldset className="mt-4">
                <legend className="text-sm font-medium">{t('What will you show the camera?')}</legend>
                <div className="mt-2 flex flex-wrap gap-2">
                  {info.data.attack_types.map((a) => (
                    <button key={a} type="button" aria-pressed={attack === a} onClick={() => setAttack(a)}
                      className={cn('rounded-full border px-3 py-1.5 text-sm transition-colors',
                        attack === a ? 'border-danger bg-danger/10 text-danger' : 'border-border hover:bg-card-hover')}>
                      {spoofLabel(a)}
                    </button>
                  ))}
                </div>
              </fieldset>
            )}
            <button type="button" disabled={!ready} onClick={() => setStage('intro')}
              className="mt-6 h-12 w-full rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 font-medium text-white shadow-lg shadow-indigo-500/20 transition-opacity disabled:opacity-40">
              {t('Continue')}
            </button>
            {!ready && <p className="mt-2 text-center text-xs text-muted">{label === 'FAKE' ? t('Choose what you will show the camera.') : t('Select a label above to continue.')}</p>}
          </section>
        )}

        {info.data && stage === 'intro' && (
          <section aria-labelledby="intro-title">
            <h1 id="intro-title" className="mt-4 text-center text-lg font-semibold">{t('Before you start')}</h1>
            <div className="mt-4 rounded-2xl border border-border bg-card p-5 shadow-sm">
              <ClipboardList className="mx-auto size-7 text-muted" aria-hidden />
              <h2 className="mt-2 text-center font-semibold">{t('Keep in mind')}</h2>
              <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-muted">
                <li><strong className="text-fg">{t('Do not move your head')}</strong> — {t('during the colour test, keep your face steady.')}</li>
                <li><strong className="text-fg">{t('Turn your screen brightness all the way up')}</strong> — {t('this improves the colour reflection and image quality.')}</li>
                <li><strong className="text-fg">{t('Follow the instructions on screen')}</strong> — {t('turn your head, move closer and hold still when asked.')}</li>
              </ol>
              <label className="mt-4 flex cursor-pointer items-start gap-2.5 rounded-lg bg-bg p-3 text-sm">
                <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} className="mt-0.5 size-4 accent-[var(--color-primary)]" />
                <span>{t('I agree that frames from this recording are stored with the label I chose, to train a fake-face detector. My name is not recorded.')}</span>
              </label>
            </div>
            <button type="button" disabled={!consent} onClick={() => { setError(null); setStage('camera') }}
              className="mt-6 h-12 w-full rounded-xl bg-gradient-to-r from-indigo-500 to-violet-600 font-medium text-white shadow-lg shadow-indigo-500/20 disabled:opacity-40">
              {t('Start')}
            </button>
            <button type="button" onClick={home} className="mt-3 w-full text-sm text-muted hover:text-fg">{t('Back')}</button>
          </section>
        )}

        {info.data && (stage === 'camera' || stage === 'flash' || stage === 'upload') && label && (
          <Capture token={token} label={label} attack={attack} stepSeconds={info.data.step_seconds} stage={stage} setStage={setStage}
            onBack={home} onDone={(r) => { setResult(r); setStage('result') }} onError={(e) => { setError(e); setStage('intro') }} />
        )}

        {stage === 'result' && result && (
          <ResultCard result={result} onRetry={() => { setResult(null); setStage('intro') }} onHome={home} />
        )}
        {error && stage === 'intro' && <p role="alert" className="mt-4 rounded-lg border border-danger/30 bg-danger/10 p-3 text-sm text-danger">{error}</p>}
      </main>
    </div>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="grid min-h-[60vh] place-items-center text-center"><div className="flex flex-col items-center">{children}</div></div>
}

function LabelCard({ selected, onSelect, icon: Icon, title, text, tone }: {
  selected: boolean; onSelect: () => void; icon: typeof UserCheck; title: string; text: string; tone: 'success' | 'danger'
}) {
  return (
    <button type="button" role="radio" aria-checked={selected} onClick={onSelect}
      className={cn('flex items-center gap-4 rounded-2xl border-2 bg-card p-4 text-left transition-colors',
        selected ? (tone === 'success' ? 'border-success bg-success/5' : 'border-danger bg-danger/5') : 'border-border hover:bg-card-hover')}>
      <span className={cn('grid size-12 shrink-0 place-items-center rounded-xl', tone === 'success' ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger')}>
        <Icon className="size-6" />
      </span>
      <span><span className="block font-semibold">{title}</span><span className="block text-sm text-muted">{text}</span></span>
    </button>
  )
}

/** Camera steps, colour flashes and upload. */
function Capture({ token, label, attack, stepSeconds, stage, setStage, onBack, onDone, onError }: {
  token: string; label: CollectLabel; attack: string | null; stepSeconds: number; stage: Stage
  setStage: (s: Stage) => void; onBack: () => void; onDone: (r: CollectResult) => void; onError: (msg: string) => void
}) {
  const { t } = useT()
  const cam = useCamera(COLLECT_SIZE)
  const [frame, setFrame] = useState<CollectFrame | null>(null)
  const [step, setStep] = useState<Step>('POSITION')
  const [progress, setProgress] = useState(0)
  const [flash, setFlash] = useState(-1)
  const [uploadPct, setUploadPct] = useState<number | null>(null)
  const steps = useRef<Step[]>([])
  const stepStart = useRef(0)
  const base = useRef<{ w: number; cx: number; cy: number } | null>(null)
  const held = useRef(0)
  const recorder = useRef<MediaRecorder | null>(null)
  const chunks = useRef<Blob[]>([])
  const recStart = useRef(0)
  const busy = useRef(false)
  const finished = useRef(false)

  useEffect(() => {
    steps.current = Math.random() < 0.5 ? ['TURN_RIGHT', 'TURN_LEFT', 'CLOSER', 'STILL'] : ['TURN_LEFT', 'TURN_RIGHT', 'CLOSER', 'STILL']
    void cam.start()
    return () => { recorder.current?.state === 'recording' && recorder.current.stop() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  useEffect(() => { if (cam.status === 'error' && cam.error) onError(cam.error) }, [cam.status, cam.error, onError])

  const upload = useCallback(async (blob: Blob) => {
    setStage('upload')
    try {
      onDone(await submitCollect(token, blob, label, participantId(), label === 'FAKE' ? attack : null, setUploadPct))
    } catch (e) {
      onError(errorMessage(e))
    } finally {
      cam.stop()
    }
  }, [token, label, attack, setStage, onDone, onError, cam])

  const startRecording = useCallback(() => {
    const stream = cam.videoRef.current?.srcObject
    const mimeType = pickMime()
    if (!(stream instanceof MediaStream) || !mimeType) { onError(t('This browser cannot record video (MediaRecorder is unavailable).')); return false }
    chunks.current = []
    const rec = new MediaRecorder(stream, { mimeType, videoBitsPerSecond: 700_000 })
    rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data)
    rec.onstop = () => void upload(new Blob(chunks.current, { type: rec.mimeType || mimeType }))
    rec.start(500)
    recorder.current = rec
    recStart.current = performance.now()
    return true
  }, [cam.videoRef, onError, t, upload])

  const runFlash = useCallback(() => {
    if (finished.current) return
    finished.current = true
    setStage('flash')
    FLASH.forEach((_, i) => window.setTimeout(() => setFlash(i), i * FLASH_MS))
    window.setTimeout(() => { setFlash(-1); recorder.current?.stop() }, FLASH.length * FLASH_MS + 300)
  }, [setStage])

  const next = useCallback(() => {
    const rest = steps.current
    held.current = 0
    base.current = null
    setProgress(0)
    if (!rest.length || performance.now() - recStart.current > MAX_RECORD_MS) { runFlash(); return }
    setStep(rest[0])
    steps.current = rest.slice(1)
    stepStart.current = performance.now()
  }, [runFlash])

  // ~4 frames per second of live guidance while the steps run
  useEffect(() => {
    if (cam.status !== 'active' || stage !== 'camera') return
    const id = window.setInterval(async () => {
      const video = cam.videoRef.current
      if (busy.current || !video || video.readyState < 2) return
      busy.current = true
      try {
        const f = await sendCollectFrame(token, await frameToBlob(video, 360, 0.7))
        setFrame(f)
        advance(f)
      } catch { /* a dropped frame is fine */ } finally { busy.current = false }
    }, 250)
    return () => window.clearInterval(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam.status, stage, step])

  function advance(f: CollectFrame) {
    const one = f.face_count === 1 && f.box
    const elapsed = (performance.now() - stepStart.current) / 1000
    if (step === 'POSITION') {
      if (!one) { held.current = 0; setProgress(0); return }
      const cx = f.box!.x + f.box!.w / 2, cy = f.box!.y + f.box!.h / 2
      const inside = Math.abs(cx - 0.5) < 0.18 && Math.abs(cy - 0.5) < 0.22 && f.box!.w > 0.18
      held.current = inside ? held.current + 1 : 0
      setProgress(clamp01(held.current / 3))
      if (held.current >= 3 && startRecording()) next()
      return
    }
    if (elapsed > stepSeconds) { next(); return } // never get stuck: a spoof attempt may not be able to do every step
    if (!one) return
    if (step === 'TURN_RIGHT' || step === 'TURN_LEFT') {
      if (f.yaw == null) return
      const want = step === 'TURN_LEFT' ? 1 : -1 // raw camera image: the participant's left is +yaw
      const p = clamp01((f.yaw * want) / TURN)
      setProgress(p)
      held.current = p >= 1 ? held.current + 1 : 0
      if (held.current >= 2) next()
    } else if (step === 'CLOSER') {
      base.current ??= { w: f.box!.w, cx: 0, cy: 0 }
      const target = Math.min(0.9, Math.max(base.current.w * 1.3, base.current.w + 0.08))
      const p = clamp01((f.box!.w - base.current.w) / (target - base.current.w))
      setProgress(p)
      if (p >= 1) next()
    } else if (step === 'STILL') {
      const cx = f.box!.x + f.box!.w / 2, cy = f.box!.y + f.box!.h / 2
      base.current ??= { w: f.box!.w, cx, cy }
      const moved = Math.hypot(cx - base.current.cx, cy - base.current.cy) > 0.06
      held.current = moved ? 0 : held.current + 1
      if (moved) base.current = { w: f.box!.w, cx, cy }
      setProgress(clamp01(held.current / 6))
      if (held.current >= 6) next()
    }
  }

  const loading = cam.status !== 'active' ? t('Starting the camera…') : !frame ? t('Loading the model…') : null
  const text = t(STEP_TEXT[step])
  const labelName = label === 'REAL' ? t('Genuine') : t('Fake')

  return (
    <section aria-live="polite">
      <button type="button" onClick={() => { cam.stop(); onBack() }}
        className="mx-auto mb-4 mt-1 flex items-center gap-1 rounded-full bg-indigo-500/10 px-3 py-1.5 text-xs font-medium text-indigo-600 dark:text-indigo-300">
        <ChevronLeft className="size-3.5" />{t('You are on the {label} page', { label: labelName })}
      </button>
      <div className="relative mx-auto aspect-[3/4.6] w-[74%] max-w-[290px] overflow-hidden rounded-[9999px] bg-black shadow-xl ring-4 ring-border">
        <video ref={cam.videoRef} playsInline muted className="size-full -scale-x-100 object-cover" />
        {(loading || stage === 'upload') && (
          <div className="absolute inset-0 grid place-items-center bg-black/80 text-center text-sm text-white">
            <div className="flex flex-col items-center gap-3 px-6">
              <Loader2 className="size-8 animate-spin text-indigo-300" />
              {stage === 'upload' ? (uploadPct != null && uploadPct < 100 ? t('Uploading {pct}%', { pct: uploadPct }) : t('Processing the result…')) : loading}
            </div>
          </div>
        )}
        {!loading && stage === 'camera' && (
          <div className="absolute inset-x-0 top-[7%] flex flex-col items-center gap-1.5 px-[18%]">
            <p className="rounded-xl bg-gradient-to-b from-indigo-500 to-violet-600 px-3 py-2 text-center text-xs font-medium text-white shadow-lg">{text}</p>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/30" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}>
              <div className="h-full rounded-full bg-indigo-400 transition-[width] duration-200" style={{ width: `${progress * 100}%` }} />
            </div>
          </div>
        )}
      </div>
      <p className="mt-5 text-center font-medium">{stage === 'upload' ? t('Processing the result…') : loading ?? text}</p>
      {stage === 'camera' && frame && frame.face_count !== 1 && (
        <p className="mt-1 text-center text-sm text-warning">{frame.face_count === 0 ? t('No face found. Look at the camera.') : t('Only one person should be in the frame.')}</p>
      )}
      {stage === 'flash' && (
        <div className="fixed inset-0 z-50 flex items-start justify-center transition-colors duration-100" style={{ background: FLASH[Math.max(0, flash)] }}>
          <p className="mt-[18vh] px-6 text-center text-xl font-semibold text-white [text-shadow:0_1px_6px_rgba(0,0,0,.55)]">{t('Keep your face still')}</p>
        </div>
      )}
    </section>
  )
}

function ResultCard({ result, onRetry, onHome }: { result: CollectResult; onRetry: () => void; onHome: () => void }) {
  const { t } = useT()
  const s = result.score
  const title = !s ? t('Recording saved') : s.status === 'REAL' ? t('Real person detected') : s.status === 'FAKE' ? t('Fake detected') : t('Not conclusive')
  const tone = !s ? 'primary' : s.status === 'REAL' ? 'success' : s.status === 'FAKE' ? 'danger' : 'warning'
  const toneCls = { primary: 'border-primary/40 text-primary', success: 'border-success/40 text-success', danger: 'border-danger/40 text-danger', warning: 'border-warning/40 text-warning' }[tone]
  return (
    <section className="mt-4">
      <div className={cn('rounded-2xl border-2 bg-card p-5 shadow-sm', toneCls)}>
        <h1 className="text-center text-lg font-semibold">{title}</h1>
        <p className="mt-3 rounded-xl border border-border bg-bg py-4 text-center text-3xl font-bold tabular-nums text-fg">
          {s ? `${(s.bona_fide_score * 100).toFixed(2)}%` : result.added}
        </p>
        <dl className="mt-4 space-y-2 text-sm text-fg">
          <Row k={s ? t('Score') : t('Frames saved')} v={s ? `${(s.bona_fide_score * 100).toFixed(2)}% (${t('threshold')} ${s.threshold.toFixed(2)})` : String(result.added)} />
          <Row k={t('Status')} v={translateServer(result.message)} />
          <Row k={t('Type')} v={result.group === 'LIVE' ? t('Live person') : spoofLabel(result.group)} />
          {s && <Row k={t('Model')} v={s.model} />}
        </dl>
      </div>
      <button type="button" onClick={onRetry} className="mt-5 h-11 w-full rounded-xl bg-gradient-to-r from-sky-500 to-blue-600 font-medium text-white">{t('Try again')}</button>
      <button type="button" onClick={onHome} className="mt-3 h-11 w-full rounded-xl bg-muted/25 font-medium">{t('Home')}</button>
    </section>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="rounded-lg border-l-4 border-current/30 bg-bg px-3 py-2">
      <dt className="text-xs font-semibold">{k}:</dt>
      <dd className="mt-0.5 font-mono text-xs text-muted">{v}</dd>
    </div>
  )
}
