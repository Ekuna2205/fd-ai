import { Info } from 'lucide-react'
import { Link } from 'react-router-dom'
import { StatusBadge } from '@/components/StatusBadge'
import { Card, CardHeader } from '@/components/ui/card'
import { QualityList } from '@/components/verify/QualityList'
import { ScoreBar } from '@/components/verify/ScoreBar'
import type { VerificationResult } from '@/types/face'
import { formatDateTime, formatMs, formatPercent } from '@/utils/format'
import { translateServer, useT } from '@/i18n'
import { spoofLabel } from '@/i18n/labels'

// Statuses where a model could have produced a verdict (no-face / multi-face results are never scored).
const SCOREABLE = new Set<VerificationResult['status']>(['REAL', 'FAKE', 'UNCERTAIN'])
const MODE: Record<VerificationResult['mode'], string> = { LIVE: 'Live camera', UPLOAD_IMAGE: 'Image upload', UPLOAD_VIDEO: 'Video upload' }

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="flex items-start justify-between gap-4 py-2 text-sm"><dt className="text-muted">{label}</dt><dd className="text-right">{children}</dd></div>
}

export function ResultPanel({ result, linkToDetail }: { result: VerificationResult; linkToDetail?: boolean }) {
  const { t } = useT()
  const v = result.video
  return (
    <Card>
      <CardHeader title={t('Verification result')} description={formatDateTime(result.created_at)} action={<StatusBadge status={result.status} />} />
      <div className="space-y-4 p-5">
        {result.explanation && <p className="text-sm leading-relaxed">{translateServer(result.explanation)}</p>}
        {result.score && <ScoreBar score={result.score} />}
        {!result.score && SCOREABLE.has(result.status) && (
          <div className="flex gap-2.5 rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
            <Info className="mt-0.5 size-4 shrink-0" />
            <p><strong className="font-medium">{t('Liveness was not assessed.')}</strong> {result.liveness.available ? t('No anti-spoofing model was active when this sample was analysed.') : translateServer(result.liveness.reason)} {t('Face detection and quality checks alone cannot show that a person is live.')}</p>
          </div>
        )}
        <dl className="divide-y divide-border">
          <Row label={t('Verification ID')}><span className="break-all font-mono text-xs">{result.id}</span></Row>
          <Row label={t('Source')}>{t(MODE[result.mode])}</Row>
          <Row label={t('Faces detected')}>{result.face_count ?? '—'}</Row>
          <Row label={t('Spoof category')}>{result.spoof_type ? spoofLabel(result.spoof_type) : t('Not assessed')}</Row>
          <Row label={t('Confidence')}>{result.confidence == null ? t('Not available') : formatPercent(result.confidence)}</Row>
          <Row label={t('Model version')}>{result.model_version ?? t('None')}</Row>
          <Row label={t('Processing time')}>{formatMs(result.processing_ms)}</Row>
        </dl>
        {v && (
          <div>
            <p className="mb-1 text-sm font-medium">{t('Video summary')}</p>
            <dl className="divide-y divide-border">
              <Row label={t('Frames analysed')}>{v.frames_analyzed}{v.duration_seconds != null && <span className="text-muted"> · {v.duration_seconds}s</span>}</Row>
              <Row label={t('Single face / none / multiple')}>{v.frames_single_face} / {v.frames_no_face} / {v.frames_multiple_faces}</Row>
              <Row label={t('Quality checks passed')}>{formatPercent(v.quality_pass_ratio)}</Row>
              <Row label={t('Face position jitter')}>{v.position_jitter ?? '—'}</Row>
              <Row label={t('Face size variation')}>{v.size_variation ?? '—'}</Row>
            </dl>
            <p className="mt-1 text-xs text-muted">{t('Temporal measurements are descriptive; only the anti-spoofing score above is used for a decision.')}</p>
          </div>
        )}
        {result.quality && <div><p className="mb-1 text-sm font-medium">{t('Image quality')}</p><div className="-mx-5"><QualityList quality={result.quality} /></div></div>}
        <p className="text-xs text-muted">{t('This result supports human review. It is not a basis for high-impact decisions on its own.')}</p>
        {linkToDetail && <Link to={`/verifications/${result.id}`} className="text-sm font-medium text-primary hover:underline">{t('Open full record')}</Link>}
      </div>
    </Card>
  )
}
