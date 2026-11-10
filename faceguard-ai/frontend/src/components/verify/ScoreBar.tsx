import type { LivenessScore } from '@/types/face'
import { formatPercent } from '@/utils/format'
import { useT } from '@/i18n'

/** Bona fide score on a 0–100% track: the threshold as a tick, the "no verdict" band shaded around it. */
export function ScoreBar({ score }: { score: LivenessScore }) {
  const { t } = useT()
  const pct = (v: number) => `${Math.min(100, Math.max(0, v * 100))}%`
  const lo = Math.max(0, score.threshold - score.uncertainty_margin)
  const hi = Math.min(1, score.threshold + score.uncertainty_margin)
  const tone = score.bona_fide_score >= hi ? 'bg-success' : score.bona_fide_score <= lo ? 'bg-danger' : 'bg-warning'
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-3 text-sm">
        <span className="font-medium">{t('Anti-spoofing score')}</span>
        <span className="tabular-nums">{formatPercent(score.bona_fide_score)} <span className="text-xs text-muted">{t('bona fide')}</span></span>
      </div>
      <div
        className="relative h-2.5 rounded-full bg-border"
        role="meter" aria-label={t('Bona fide score')} aria-valuemin={0} aria-valuemax={1} aria-valuenow={score.bona_fide_score}
      >
        <div className="absolute inset-y-0 rounded-full bg-warning/25" style={{ left: pct(lo), width: pct(hi - lo) }} title={t('No verdict in this band')} />
        <div className={`absolute inset-y-0 left-0 rounded-full ${tone}`} style={{ width: pct(score.bona_fide_score) }} />
        <div className="absolute -inset-y-1 w-0.5 rounded bg-fg" style={{ left: pct(score.threshold) }} title={t('Threshold {value}', { value: score.threshold.toFixed(2) })} />
      </div>
      <div className="mt-1 flex justify-between text-[11px] text-muted">
        <span>{t('Attack')}</span>
        <span>{t('threshold {value} ± {margin}', { value: score.threshold.toFixed(2), margin: score.uncertainty_margin.toFixed(2) })}</span>
        <span>{t('Bona fide')}</span>
      </div>
      <p className="mt-1 text-xs text-muted">
        {score.model}{score.frames_scored > 1 ? ` · ${t('mean of {n} frames', { n: score.frames_scored })}` : ''}. {t('Scores are uncalibrated model output, not a probability that the person is real.')}
      </p>
    </div>
  )
}
