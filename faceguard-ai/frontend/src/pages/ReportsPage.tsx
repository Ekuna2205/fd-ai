import { useQuery } from '@tanstack/react-query'
import { Activity, BarChart3, CheckCircle2, Download, HelpCircle, Percent, ShieldAlert, Timer, XCircle } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { CategoryChart } from '@/components/charts/CategoryChart'
import { DistributionChart } from '@/components/charts/DistributionChart'
import { SeriesChart } from '@/components/charts/SeriesChart'
import { PageHeader } from '@/components/PageHeader'
import { StatCard } from '@/components/StatCard'
import { Button } from '@/components/ui/button'
import { Card, CardHeader } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { EmptyState, ErrorState } from '@/components/ui/state'
import { useAuth } from '@/hooks/useAuth'
import { errorMessage } from '@/services/api'
import { exportReport, getReport } from '@/services/history'
import type { Period } from '@/types/history'
import { formatMs, formatNumber, formatPercent } from '@/utils/format'
import { useT } from '@/i18n'

export default function ReportsPage() {
  const { t } = useT()
  const { user } = useAuth()
  const isAdmin = user?.role === 'administrator'
  const [period, setPeriod] = useState<Period>('day')
  const [days, setDays] = useState(30)
  const [scope, setScope] = useState<'own' | 'all'>('own')
  const [busy, setBusy] = useState(false)
  const rep = useQuery({ queryKey: ['report', period, days, scope], queryFn: () => getReport(period, days, scope), retry: false })
  const tot = rep.data?.totals
  const PERIOD_DESC = { day: 'Per day, last {n} days (UTC)', week: 'Per week, last {n} days (UTC)', month: 'Per month, last {n} days (UTC)' } as const

  async function download() {
    setBusy(true)
    try { await exportReport(period, days, scope); toast.success(t('Report downloaded.')) } catch (e) { toast.error(errorMessage(e)) } finally { setBusy(false) }
  }

  return (
    <div className="space-y-6">
      <PageHeader title={t('Reports')} description={scope === 'all' ? t('Aggregate counts for all users (no individual records).') : t('Statistics for your own verifications.')}
        actions={<Button variant="outline" onClick={download} disabled={busy || !tot?.attempts}><Download className="size-4" />{busy ? t('Preparing…') : t('Export CSV')}</Button>} />

      <Card className="grid gap-3 p-4 sm:grid-cols-3">
        <Select label={t('Group by')} value={period} onChange={(e) => setPeriod(e.target.value as Period)}><option value="day">{t('Day')}</option><option value="week">{t('Week')}</option><option value="month">{t('Month')}</option></Select>
        <Select label={t('Time range')} value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 30, 90, 365].map((d) => <option key={d} value={d}>{t('Last {n} days', { n: d })}</option>)}</Select>
        {isAdmin && <Select label={t('Scope')} value={scope} onChange={(e) => setScope(e.target.value as 'own' | 'all')}><option value="own">{t('My verifications')}</option><option value="all">{t('All users (aggregate)')}</option></Select>}
      </Card>

      {rep.isError && <ErrorState title={t('Report unavailable')} message={errorMessage(rep.error)} onRetry={() => void rep.refetch()} />}

      <section aria-label={t('Totals')} className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
        <StatCard loading={rep.isLoading} label={t('Attempts')} icon={Activity} value={tot ? formatNumber(tot.attempts) : '—'} />
        <StatCard loading={rep.isLoading} label={t('Real')} icon={CheckCircle2} tone="text-success" value={tot ? formatNumber(tot.real) : '—'} />
        <StatCard loading={rep.isLoading} label={t('Fake')} icon={ShieldAlert} tone="text-danger" value={tot ? formatNumber(tot.fake) : '—'} />
        <StatCard loading={rep.isLoading} label={t('Uncertain')} icon={HelpCircle} tone="text-warning" value={tot ? formatNumber(tot.uncertain) : '—'} />
        <StatCard loading={rep.isLoading} label={t('Failed')} icon={XCircle} tone="text-danger" value={tot ? formatNumber(tot.failed) : '—'} />
        <StatCard loading={rep.isLoading} label={t('Real share')} icon={Percent} tone="text-secondary" value={tot ? formatPercent(tot.success_rate) : '—'} />
        <StatCard loading={rep.isLoading} label={t('Avg. duration')} icon={Timer} value={rep.data ? formatMs(rep.data.avg_processing_ms) : '—'} />
      </section>

      <Card>
        <CardHeader title={t('Outcomes over time')} description={t(PERIOD_DESC[period], { n: days })} />
        <div className="p-4">{rep.isLoading ? <Skeleton className="h-72" /> : rep.data && rep.data.series.length > 0 ? <SeriesChart data={rep.data.series} period={period} />
          : <EmptyState icon={BarChart3} title={t('No verifications in this period')} hint={t('Pick a longer time range, or run a verification.')} />}</div>
      </Card>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader title={t('Result distribution')} /><div className="p-4">{rep.isLoading ? <Skeleton className="h-52" /> : tot && tot.attempts > 0
          ? <DistributionChart real={tot.real} fake={tot.fake} uncertain={tot.uncertain} /> : <EmptyState icon={BarChart3} title={t('Nothing to chart')} />}</div></Card>
        <Card><CardHeader title={t('Spoof categories')} description={t('Only where a trained model predicts the type')} /><div className="p-4">{rep.isLoading ? <Skeleton className="h-52" /> : rep.data && rep.data.spoof_categories.length > 0
          ? <CategoryChart data={rep.data.spoof_categories} /> : <EmptyState icon={ShieldAlert} title={t('No attacks categorised')} hint={t('Categories need a trained model that predicts attack type.')} />}</div></Card>
      </section>
      <p className="text-xs text-muted">{t('Real share = real results ÷ all finished attempts. Without a trained model, most results are Uncertain by design.')}</p>
    </div>
  )
}
