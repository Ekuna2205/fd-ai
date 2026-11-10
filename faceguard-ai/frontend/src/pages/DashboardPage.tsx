import { Link } from 'react-router-dom'
import { Activity, BarChart3, CheckCircle2, HelpCircle, Percent, ShieldAlert, XCircle, Boxes } from 'lucide-react'
import { CategoryChart } from '@/components/charts/CategoryChart'
import { DailyChart } from '@/components/charts/DailyChart'
import { DistributionChart } from '@/components/charts/DistributionChart'
import { StatCard } from '@/components/StatCard'
import { StatusBadge } from '@/components/StatusBadge'
import { Card, CardHeader } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, ErrorState } from '@/components/ui/state'
import { useHealth, useOverview } from '@/hooks/useDashboard'
import { errorMessage } from '@/services/api'
import { formatDateTime, formatNumber, formatPercent } from '@/utils/format'
import { useT } from '@/i18n'
import { spoofLabel } from '@/i18n/labels'

export default function DashboardPage() {
  const { t } = useT()
  const { data, isLoading, isError, error, refetch } = useOverview()
  const { data: health } = useHealth()
  const tot = data?.totals

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('Dashboard')}</h1>
        <p className="mt-1 text-sm text-muted">{t('Verification activity and model status, read from the database.')}</p>
      </div>

      {isError && (
        <ErrorState title={t('Dashboard data is unavailable')} message={errorMessage(error)} onRetry={() => refetch()}
          extra={<p className="mt-1 text-xs text-muted">{t('Check that the backend and database are running. This page shows no figures rather than invented ones.')}</p>} />
      )}

      <section aria-label={t('Totals')} className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        <StatCard loading={isLoading} label={t('Total attempts')} icon={Activity} value={tot ? formatNumber(tot.attempts) : '—'} />
        <StatCard loading={isLoading} label={t('Real')} icon={CheckCircle2} tone="text-success" value={tot ? formatNumber(tot.real) : '—'} />
        <StatCard loading={isLoading} label={t('Spoofing detected')} icon={ShieldAlert} tone="text-danger" value={tot ? formatNumber(tot.fake) : '—'} />
        <StatCard loading={isLoading} label={t('Failed')} icon={XCircle} tone="text-danger" value={tot ? formatNumber(tot.failed) : '—'} />
        <StatCard loading={isLoading} label={t('Uncertain')} icon={HelpCircle} tone="text-warning" value={tot ? formatNumber(tot.uncertain) : '—'} />
        <StatCard loading={isLoading} label={t('Success rate')} icon={Percent} tone="text-secondary" value={tot ? formatPercent(tot.success_rate) : '—'} />
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title={t('Daily verifications')} description={t('Outcomes per day, last 14 days')} />
          <div className="p-4">
            {isLoading ? <Skeleton className="h-64" /> : data && data.daily.length > 0
              ? <DailyChart data={data.daily} />
              : <EmptyState icon={BarChart3} title={t('No verifications yet')} hint={t('Daily outcomes appear here after the first verification is recorded.')} />}
          </div>
        </Card>
        <Card>
          <CardHeader title={t('Real vs fake')} description={t('Share of classified attempts')} />
          <div className="p-4">
            {isLoading ? <Skeleton className="h-64" /> : tot && tot.real + tot.fake + tot.uncertain > 0
              ? <DistributionChart real={tot.real} fake={tot.fake} uncertain={tot.uncertain} />
              : <EmptyState icon={BarChart3} title={t('Nothing to chart')} hint={t('No classified attempts have been recorded.')} />}
          </div>
        </Card>
      </section>

      <section className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title={t('Spoof attack types')} description={t('Only where the model supports the category')} />
          <div className="p-4">
            {isLoading ? <Skeleton className="h-52" /> : data && data.spoof_categories.length > 0
              ? <CategoryChart data={data.spoof_categories} />
              : <EmptyState icon={ShieldAlert} title={t('No attacks categorised')} hint={t('Categories require a trained model that predicts attack type.')} />}
          </div>
        </Card>

        <Card>
          <CardHeader title={t('Active model')} description={t('Presentation attack detection')} />
          <div className="p-4">
            {isLoading ? <Skeleton className="h-40" /> : data?.active_model ? (
              <div className="space-y-4">
                <div>
                  <p className="text-sm font-medium">{data.active_model.name}</p>
                  <p className="text-xs text-muted">{t('Version {v}', { v: data.active_model.version })}</p>
                </div>
                {!data.active_model.trained && (
                  <p className="rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning">
                    {t('Baseline weights, not trained. Do not use for real decisions.')}
                  </p>
                )}
                <dl className="grid grid-cols-3 gap-2 text-center">
                  {([['APCER', data.active_model.apcer], ['BPCER', data.active_model.bpcer], ['ACER', data.active_model.acer]] as const).map(([k, v]) => (
                    <div key={k} className="rounded-lg bg-bg py-2">
                      <dt className="text-xs text-muted">{k}</dt>
                      <dd className="text-sm font-semibold tabular-nums">{formatPercent(v)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ) : <EmptyState icon={Boxes} title={t('No active model')} hint={t('Register and activate a model to enable liveness classification.')} />}
          </div>
        </Card>

        <Card>
          <CardHeader title={t('System status')} />
          <ul className="divide-y divide-border text-sm">
            {([
              ['API', health ? health.status === 'ok' : undefined],
              ['Database', health?.database],
              ['Model loaded', health?.model_loaded],
              ['Model trained', health?.model_trained],
            ] as const).map(([name, ok]) => (
              <li key={name} className="flex items-center justify-between px-5 py-3">
                <span className="text-muted">{t(name)}</span>
                <span className={ok === undefined ? 'text-muted' : ok ? 'text-success' : 'text-danger'}>
                  {ok === undefined ? t('Unknown') : ok ? t('Yes') : t('No')}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </section>

      <Card>
        <CardHeader title={t('Recent activity')} description={t('Latest verification attempts')} />
        {isLoading ? (
          <div className="space-y-3 p-5">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-5" />)}</div>
        ) : data && data.recent.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead className="text-xs text-muted">
                <tr><th className="px-5 py-2.5 font-medium">{t('Time')}</th><th className="px-5 py-2.5 font-medium">{t('Status')}</th><th className="px-5 py-2.5 font-medium">{t('Spoof type')}</th><th className="px-5 py-2.5 text-right font-medium">{t('Confidence')}</th></tr>
              </thead>
              <tbody className="divide-y divide-border">
                {data.recent.map((r) => (
                  <tr key={r.id}>
                    <td className="px-5 py-3"><Link to={`/verifications/${r.id}`} className="text-muted hover:text-primary hover:underline">{formatDateTime(r.created_at)}</Link></td>
                    <td className="px-5 py-3"><StatusBadge status={r.status} /></td>
                    <td className="px-5 py-3 text-muted">{spoofLabel(r.spoof_type)}</td>
                    <td className="px-5 py-3 text-right tabular-nums">{formatPercent(r.confidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <EmptyState icon={Activity} title={t('No activity yet')} hint={t('Run a verification to see it listed here.')} />}
      </Card>
    </div>
  )
}
